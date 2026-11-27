/* ===================================================================
 * Form Validation
 *
 * Client-side validation using HTML constraint validation and
 * validation messages supplied by WTForms through data attributes.
 *
 * Supports:
 * - Required fields
 * - Minimum and maximum lengths
 * - Email and URL inputs
 * - Regular expression patterns
 * - Numeric ranges and steps
 * - File extensions and file sizes
 * - Server-rendered validation errors
 *
 * ------------------------------------------------------------------- */

const FORM_SELECTOR = [
    'form[data-bs-validate]',
    'form[data-live-validation]'
].join(',')

const FIELD_SELECTOR = 'input, select, textarea'


/* -------------------------------------------------------------------
 * Helpers
 * ------------------------------------------------------------------- */

const getFields = (form) => {
    return Array.from(form.elements).filter((field) => {
        return field.matches?.(FIELD_SELECTOR) &&
            field.willValidate
    })
}


const getFeedbackElement = (field) => {
    if (!field.id) return null

    const feedbackId = field.dataset.feedbackTarget ||
        `${field.id}-feedback`

    return document.getElementById(feedbackId)
}


const getFieldValue = (field) => {
    if (field.type === 'file') {
        return Array.from(field.files || [])
            .map(file => `${file.name}:${file.size}:${file.lastModified}`)
            .join('|')
    }

    if (field.type === 'checkbox' || field.type === 'radio') {
        return String(field.checked)
    }

    return field.value
}


const addDescribedBy = (field, feedback) => {
    if (!feedback) return

    const ids = new Set(
        (field.getAttribute('aria-describedby') || '')
            .split(/\s+/)
            .filter(Boolean)
    )

    ids.add(feedback.id)

    field.setAttribute(
        'aria-describedby',
        Array.from(ids).join(' ')
    )
}


/* -------------------------------------------------------------------
 * Required Validation
 * ------------------------------------------------------------------- */

const isRequiredEmpty = (field) => {
    if (!field.disabled || !field.required) {
        return false
    }

    if (field.type === 'file') {
        return !field.files?.length
    }

    if (field.type === 'checkbox' || field.type === 'radio') {
        return !field.checked
    }

    // Match WTForms DataRequired behaviour for whitespace-only text.
    if (
        field.tagName === 'INPUT' &&
        ['text', 'email', 'url', 'tel', 'search', 'password'].includes(field.type)
    ) {
        return field.value.trim() === ''
    }

    if (field.tagName === 'TEXTAREA') {
        return field.value.trim() === ''
    }

    if (field.tagName === 'SELECT') {
        return field.value === ''
    }

    return field.validity.valueMissing
}


/* -------------------------------------------------------------------
 * Native Constraint Validation
 * ------------------------------------------------------------------- */

const getConstraintMessage = (field) => {
    const validity = field.validity
    const messages = field.dataset

    // Required fields.
    if (validity.valueMissing || isRequiredEmpty(field)) {
        return messages.msgRequired || field.validationMessage
    }

    // Match browser constraint failures to WTForms messages.
    const rules = [
        [validity.tooShort, messages.msgTooShort],
        [validity.tooLong, messages.msgTooLong],
        [validity.typeMismatch, messages.msgTypeMismatch],
        [validity.patternMismatch, messages.msgPatternMismatch],

        [
            validity.rangeUnderflow,
            messages.msgRangeUnderflow || messages.msgRange
        ],

        [
            validity.rangeOverflow,
            messages.msgRangeOverflow || messages.msgRange
        ],

        [validity.stepMismatch, messages.msgStepMismatch],
        [validity.badInput, messages.msgBadInput],
    ]

    for (const [failed, message] of rules) {
        if (failed) {
            return message || field.validationMessage
        }
    }

    // Preserve errors assigned through setCustomValidity elsewhere.
    if (validity.customError) {
        return field.validationMessage
    }

    return validity.valid ? '' : field.validationMessage
}


/* -------------------------------------------------------------------
 * File Validation
 * ------------------------------------------------------------------- */

const fileMatchesAccept = (file, rule) => {
    const value = rule.toLowerCase()
    const extension = file.name
        .split('.')
        .pop()
        .toLowerCase()

    const mimeType = (file.type || '').toLowerCase()

    // Explicit file extensions, e.g. .jpg or .png.
    if (value.startsWith('.')) {
        return `.${extension}` === value
    }

    // Wildcard MIME types, e.g. image/*.
    if (value.endsWith('/*')) {
        return mimeType.startsWith(value.slice(0, -1))
    }

    // Explicit MIME types.
    return mimeType === value
}


const getFileValidationMessage = (field) => {
    if (field.type !== 'file') return ''

    const files = Array.from(field.files || [])

    if (!files.length) return ''

    const messages = field.dataset

    // Maximum file size.
    if (messages.maxSizeBytes !== undefined) {
        const maxSize = Number(messages.maxSizeBytes)

        if (
            Number.isFinite(maxSize) &&
            files.some(file => file.size > maxSize)
        ) {
            return messages.msgFileTooLarge || field.validationMessage
        }
    }

    // Allowed file extensions / MIME types.
    const accept = field.getAttribute('accept')

    if (accept) {
        const acceptedTypes = accept
            .split(',')
            .map(value => value.trim())
            .filter(Boolean)

        const hasInvalidFile = files.some(file => {
            return !acceptedTypes.some(rule => {
                return fileMatchesAccept(file, rule)
            })
        })

        if (hasInvalidFile) {
            return messages.msgInvalidFile || field.validationMessage
        }
    }

    return ''
}


/* -------------------------------------------------------------------
 * Validation Messages
 * ------------------------------------------------------------------- */

const getValidationMessage = (field) => {
    // Check native constraints first.
    const constraintMessage = getConstraintMessage(field)

    if (constraintMessage) {
        return constraintMessage
    }

    // Then check constraints not supported natively by HTML.
    return getFileValidationMessage(field)
}


/* -------------------------------------------------------------------
 * Feedback
 * ------------------------------------------------------------------- */

const updateFeedback = (field, message) => {
    const feedback = getFeedbackElement(field)
    const invalid = Boolean(message)

    // Bootstrap validation styling.
    field.classList.toggle('is-invalid', invalid)

    if (invalid) {
        field.setAttribute('aria-invalid', 'true')
    } else {
        field.removeAttribute('aria-invalid')
    }

    if (!feedback) return

    feedback.textContent = message
    feedback.classList.toggle('d-block', invalid)
}


/* -------------------------------------------------------------------
 * Field Validation
 * ------------------------------------------------------------------- */

// Preserve server-side errors until the user changes the field.
// This matters for Python validators such as phone-number validation
// and address/geocoding checks that cannot be reproduced in JavaScript.

const serverErrors = new WeakMap()


const validateField = (field) => {
    const serverError = serverErrors.get(field)
    const currentValue = getFieldValue(field)

    let message = ''

    if (serverError && serverError.value === currentValue) {
        message = serverError.message
    } else {
        // The user changed the field, so the old server error is stale.
        serverErrors.delete(field)

        message = getValidationMessage(field)
    }

    updateFeedback(field, message)

    return !message
}


/* -------------------------------------------------------------------
 * Form Validation
 * ------------------------------------------------------------------- */

const initialiseForm = (form) => {
    if (form.dataset.validationInitialised === 'true') return

    form.dataset.validationInitialised = 'true'

    const fields = getFields(form)

    // Initialise fields and detect server-rendered errors.
    fields.forEach((field) => {
        const feedback = getFeedbackElement(field)

        addDescribedBy(field, feedback)

        const serverMessage = feedback?.textContent.trim()

        if (serverMessage) {
            serverErrors.set(field, {
                value: getFieldValue(field),
                message: serverMessage,
            })

            field.dataset.touched = 'true'

            // Apply validation styling to server-rendered errors.
            field.classList.add('is-invalid')
            field.setAttribute('aria-invalid', 'true')
        }
    })


    // ---------------------------------------------------------------
    // Input: Validate while the user types, once the field is touched.
    // ---------------------------------------------------------------

    form.addEventListener('input', (event) => {
        const field = event.target

        if (
            !field.matches(FIELD_SELECTOR) ||
            !field.willValidate
        ) {
            return
        }

        if (
            field.dataset.touched === 'true' ||
            form.dataset.submitted === 'true' ||
            serverErrors.has(field)
        ) {
            validateField(field)
        }
    })


    // ---------------------------------------------------------------
    // Change: Handles selects, files, ranges and other controls.
    // ---------------------------------------------------------------

    form.addEventListener('change', (event) => {
        const field = event.target

        if (
            !field.matches(FIELD_SELECTOR) ||
            !field.willValidate
        ) {
            return
        }

        field.dataset.touched = 'true'

        validateField(field)
    })


    // ---------------------------------------------------------------
    // Focus out: Validate when the user leaves a field.
    // ---------------------------------------------------------------

    form.addEventListener('focusout', (event) => {
        const field = event.target

        if (
            !field.matches(FIELD_SELECTOR) ||
            !field.willValidate
        ) {
            return
        }

        field.dataset.touched = 'true'

        validateField(field)
    })


    // ---------------------------------------------------------------
    // Submit: Validate every field.
    // ---------------------------------------------------------------

    form.addEventListener('submit', (event) => {
        form.dataset.submitted = 'true'

        let firstInvalidField = null

        getFields(form).forEach((field) => {
            if (!validateField(field) && !firstInvalidField) {
                firstInvalidField = field
            }
        })

        if (firstInvalidField) {
            event.preventDefault()
            firstInvalidField.focus()
        }
    })


    // ---------------------------------------------------------------
    // Reset: Clear client-side validation state.
    // ---------------------------------------------------------------

    form.addEventListener('reset', () => {
        requestAnimationFrame(() => {
            delete form.dataset.submitted

            fields.forEach((field) => {
                serverErrors.delete(field)

                delete field.dataset.touched

                field.classList.remove('is-invalid')
                field.removeAttribute('aria-invalid')

                const feedback = getFeedbackElement(field)

                if (feedback) {
                    feedback.textContent = ''
                    feedback.classList.remove('d-block')
                }
            })
        })
    })
}


/* -------------------------------------------------------------------
 * Initialisation
 * ------------------------------------------------------------------- */

export function initFormValidation(root = document) {
    const forms = []

    if (root.matches?.(FORM_SELECTOR)) {
        forms.push(root)
    }

    forms.push(...root.querySelectorAll(FORM_SELECTOR))

    forms.forEach(initialiseForm)
}

/*!
 * Locale — Bootstrap 6 directory template
 */

import {Chips, Datepicker} from 'bootstrap'
import {initBase, onReady} from './base.js'

// Fix Bootstrap's datepicker inside native <dialog> elements.
const initDatepickerDialogFix = () => {
    const prototype = Datepicker.prototype

    if (prototype.__dialogLayerPatched) return

    const originalBuild = prototype._buildCalendarOptions

    if (typeof originalBuild !== 'function') {
        console.error('Datepicker dialog fix: Bootstrap method not found.')
        return
    }

    // Position the popup relative to the input's CURRENT position.
    const positionPopup = (instance) => {
        if (!instance._isShown) return

        // Use the actual input, not Bootstrap's .form-adorn wrapper.
        const input = instance._element
        const dialog = input.closest('dialog[open]')
        const popup = instance._calendar?.context?.mainElement

        if (!dialog || !popup || popup === input) return

        if (popup.parentElement !== dialog) {
            console.log({
                input,
                inputParent: input.parentElement,
                popup,
                popupContainsInput: popup.contains(input),
                popupParent: popup.parentElement,
                formControl: input.closest('.form-control')
            })

            dialog.append(popup)
        }

        const inputRect = input.getBoundingClientRect()
        const dialogRect = dialog.getBoundingClientRect()

        const gap = 8

        // Coordinates relative to the dialog's content area.
        const inputTop =
            inputRect.top - dialogRect.top - dialog.clientTop

        const inputBottom =
            inputRect.bottom - dialogRect.top - dialog.clientTop

        const inputLeft =
            inputRect.left - dialogRect.left - dialog.clientLeft

        // Calendar dimensions.
        const popupWidth = popup.offsetWidth
        const popupHeight = popup.offsetHeight

        // Centre the calendar horizontally against the input.
        const centeredLeft =
            inputLeft + (inputRect.width - popupWidth) / 2

        // Keep the calendar within the dialog horizontally.
        const maxLeft = Math.max(
            gap,
            dialog.clientWidth - popupWidth - gap
        )

        const left = Math.max(
            gap,
            Math.min(centeredLeft, maxLeft)
        )

        // Available vertical space.
        const spaceAbove = inputTop
        const spaceBelow = dialog.clientHeight - inputBottom

        const fitsBelow = popupHeight + gap <= spaceBelow
        const fitsAbove = popupHeight + gap <= spaceAbove

        const openAbove =
            !fitsBelow && (fitsAbove || spaceAbove > spaceBelow)

        const desiredTop = openAbove
            ? inputTop - popupHeight - gap
            : inputBottom + gap

        // Keep the calendar within the dialog vertically.
        const maxTop = Math.max(
            gap,
            dialog.clientHeight - popupHeight - gap
        )

        const top = Math.max(
            gap,
            Math.min(desiredTop, maxTop)
        )

        popup.style.left = `${left}px`
        popup.style.top = `${top}px`
    }

    // Throttle repositioning to one update per animation frame.
    const schedulePosition = (instance) => {
        if (instance.__dialogPositionFrame != null) return

        instance.__dialogPositionFrame = requestAnimationFrame(() => {
            instance.__dialogPositionFrame = null
            positionPopup(instance)
        })
    }

    // Listen for scrolling anywhere inside the dialog.
    const bindScrollListeners = (instance, dialog) => {
        if (instance.__dialogScrollHandler) return

        const handler = () => {
            if (instance._isShown) {
                schedulePosition(instance)
            }
        }

        instance.__dialogScrollHandler = handler
        instance.__dialogElement = dialog

        // Capture catches scrolling inside .drawer-body too.
        dialog.addEventListener('scroll', handler, {
            capture: true,
            passive: true
        })

        // Also support normal page scrolling and window resizing.
        window.addEventListener('scroll', handler, {passive: true})
        window.addEventListener('resize', handler)

        instance.__dialogCloseHandler = () => instance.hide()
        dialog.addEventListener('close', instance.__dialogCloseHandler)
    }

    prototype._buildCalendarOptions = function (...args) {
        const options = originalBuild.apply(this, args)
        const originalOnShow = options.onShow

        options.onShow = (...callbackArgs) => {
            const dialog = this._element.closest('dialog[open]')

            if (!dialog) {
                originalOnShow?.(...callbackArgs)
                return
            }

            const drawerBody = dialog.querySelector('.drawer-body')

            // Preserve the drawer's current scroll position.
            const scrollTop = drawerBody?.scrollTop ?? 0
            const dialogScrollTop = dialog.scrollTop
            const windowScrollY = window.scrollY

            originalOnShow?.(...callbackArgs)

            // Undo any automatic scrolling caused by calendar focus.
            if (drawerBody) {
                drawerBody.scrollTop = scrollTop
            }

            dialog.scrollTop = dialogScrollTop
            window.scrollTo(window.scrollX, windowScrollY)

            // Reposition after the browser has completed layout.
            schedulePosition(this)

            bindScrollListeners(this, dialog)
        }

        return options
    }

    // Clean up listeners when the datepicker is disposed.
    const originalDispose = prototype.dispose

    prototype.dispose = function (...args) {
        const handler = this.__dialogScrollHandler
        const dialog = this.__dialogElement

        if (handler) {
            dialog?.removeEventListener('scroll', handler, true)
            window.removeEventListener('scroll', handler)
            window.removeEventListener('resize', handler)
        }

        if (this.__dialogCloseHandler) {
            dialog?.removeEventListener('close', this.__dialogCloseHandler)
        }

        if (this.__dialogPositionFrame != null) {
            cancelAnimationFrame(this.__dialogPositionFrame)
        }

        return originalDispose.apply(this, args)
    }

    prototype.__dialogLayerPatched = true
}

initDatepickerDialogFix()

const bindRange = (rangeId, outId, format) => {
    const range = document.getElementById(rangeId)
    const out = document.getElementById(outId)
    if (!range || !out) return

    const sync = () => {
        out.textContent = format(range.value)
    }
    range.addEventListener('input', sync)
    sync()
}

/* Hovering a listing highlights its map pin */
const initMapSync = () => {
    const pins = document.querySelectorAll('.map-pin')
    const listings = document.querySelectorAll('.listing')
    if (!pins.length || !listings.length) return

    listings.forEach((listing, i) => {
        const pin = pins[i]
        if (!pin) return
        const on = () => {
            pins.forEach((p) => p.classList.remove('is-active'));
            pin.classList.add('is-active')
        }
        listing.addEventListener('mouseenter', on)
        listing.addEventListener('focusin', on)
    })
}


const parseInitialDate = (value) => {
    const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value.trim())

    if (!match) return null

    const [, dayText, monthText, yearText] = match

    const day = Number(dayText)
    const month = Number(monthText)
    const year = Number(yearText)

    // Validate the date rather than accepting rollover dates.
    const date = new Date(year, month - 1, day)

    if (
        date.getFullYear() !== year ||
        date.getMonth() !== month - 1 ||
        date.getDate() !== day
    ) {
        return null
    }

    return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

const initOpenDatepicker = () => {
    const input = document.getElementById('openDate')
    if (!input) return

    // Capture the server-provided date before initialising Bootstrap.
    const initialValue = input.value.trim()
    const initialDate = parseInitialDate(initialValue)

    // Prevent Bootstrap from parsing the input and prematurely calling
    // calendar.set() during input-mode initialisation.
    input.value = ''

    const picker = Datepicker.getOrCreateInstance(input, {
        locale: 'en-GB',
        positionElement: input,
        selectedDates: initialDate ? [initialDate] : [],

        vcpOptions: {
            openOnFocus: false
        }
    })

    // Preserve an unrecognised value rather than silently discarding it.
    if (!initialDate && initialValue) {
        input.value = initialValue
    }

    const clearButton = document.getElementById('clearOpenDate')

    if (clearButton) {
        const syncClearButton = () => {
            clearButton.hidden = !input.value.trim()
        }

        input.addEventListener('change.bs.datepicker', syncClearButton)
        syncClearButton()

        clearButton.addEventListener('click', (event) => {
            event.preventDefault()
            event.stopPropagation()

            picker.hide()
            picker.setSelectedDates([])

            input.dispatchEvent(new Event('input', {bubbles: true}))
            input.dispatchEvent(new Event('change', {bubbles: true}))

            syncClearButton()
        })
    }
}


const copyToClipboard = async (text) => {
    // Prefer the modern Clipboard API.
    if (navigator.clipboard?.writeText) {
        try {
            await navigator.clipboard.writeText(text)
            return
        } catch (error) {
            // Fall back if clipboard permissions are unavailable.
        }
    }

    // Fallback for browsers without Clipboard API support.
    const textarea = document.createElement('textarea')

    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'

    document.body.append(textarea)

    textarea.focus()
    textarea.select()
    textarea.setSelectionRange(0, textarea.value.length)

    let copied = false

    try {
        copied = document.execCommand?.('copy') ?? false
    } finally {
        textarea.remove()
    }

    if (!copied) {
        throw new Error('Unable to copy URL to clipboard')
    }
}

const initFeaturePicker = () => {
    const picker = document.getElementById('featurePicker')
    if (!picker) return

    const container = picker.querySelector('[data-bs-chips]')
    const input = picker.querySelector('#featureInput')
    const suggestions = picker.querySelector('#featureSuggestions')
    const hiddenFields = picker.querySelector('[data-chip-values]')
    const status = picker.querySelector('#featureInputStatus')

    const options = JSON.parse(
        container.dataset.featureOptions || '[]'
    )

    const normalise = (value) => String(value)
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim()

    const optionsByName = new Map(
        options.map(option => [
            normalise(option.name),
            option
        ])
    )

    const findOption = value =>
        optionsByName.get(normalise(value))

    const chips = Chips.getOrCreateInstance(container)

    let matches = []
    let activeIndex = -1

    // Create one hidden form field for every selected feature.
    const syncHiddenFields = () => {
        hiddenFields.replaceChildren()

        for (const value of chips.getValues()) {
            const option = findOption(value)
            if (!option) continue

            const hidden = document.createElement('input')

            hidden.type = 'text'
            hidden.className = 'chip'
            hidden.name = 'features'
            hidden.value = option.slug
            hidden.readOnly = true
            hidden.hidden = true

            hiddenFields.append(hidden)
        }
    }

    // Never allow a chip that does not exist in the feature list.
    container.addEventListener('add.bs.chips', event => {
        const option = findOption(event.detail.value)

        const alreadySelected = option &&
            chips.getValues().some(
                value => normalise(value) === normalise(option.name)
            )

        if (!option || alreadySelected) {
            event.preventDefault()
        }
    })

    container.addEventListener(
        'change.bs.chips',
        syncHiddenFields
    )

    // Levenshtein distance for typo-tolerant matching.
    const editDistance = (a, b) => {
        let previous = Array.from(
            {length: b.length + 1},
            (_, i) => i
        )

        for (let i = 1; i <= a.length; i++) {
            const current = [i]

            for (let j = 1; j <= b.length; j++) {
                current[j] = Math.min(
                    current[j - 1] + 1,
                    previous[j] + 1,
                    previous[j - 1] +
                    (a[i - 1] === b[j - 1] ? 0 : 1)
                )
            }

            previous = current
        }

        return previous[b.length]
    }

    // Lower scores represent better matches.
    const scoreMatch = (name, query) => {
        const words = name.split(/\s+/)

        if (name === query) return 0

        if (name.startsWith(query)) {
            return 10 + (name.length - query.length) / 100
        }

        if (words.some(word => word.startsWith(query))) {
            return 20
        }

        if (name.includes(query)) {
            return 30 + name.indexOf(query) / 100
        }

        const distance = Math.min(
            editDistance(query, name),
            ...words.map(word => editDistance(query, word))
        )

        const threshold = Math.max(
            1,
            Math.floor(query.length * 0.35)
        )

        return distance <= threshold &&
        distance / query.length <= 0.4
            ? 40 + distance
            : Infinity
    }

    const hideSuggestions = () => {
        suggestions.hidden = true
        suggestions.replaceChildren()

        input.setAttribute('aria-expanded', 'false')
        input.removeAttribute('aria-activedescendant')

        matches = []
        activeIndex = -1
    }

    const updateActiveSuggestion = () => {
        const buttons = suggestions.querySelectorAll(
            '[role="option"]'
        )

        buttons.forEach((button, index) => {
            const active = index === activeIndex

            button.classList.toggle('is-active', active)
            button.setAttribute('aria-selected', String(active))
        })

        if (activeIndex >= 0) {
            input.setAttribute(
                'aria-activedescendant',
                `featureSuggestion-${activeIndex}`
            )

            buttons[activeIndex]?.scrollIntoView({
                block: 'nearest'
            })
        } else {
            input.removeAttribute('aria-activedescendant')
        }
    }

    // Only accept an actual option from the server-provided list.
    const selectFeature = option => {
        const alreadySelected = chips.getValues().some(
            value => normalise(value) === normalise(option.name)
        )

        if (alreadySelected) {
            input.value = ''
            hideSuggestions()
            input.focus()
            return
        }

        const chip = chips.add(option.name)

        if (!chip) return

        input.value = ''
        hideSuggestions()
        input.focus()

        if (status) {
            status.textContent = `${option.name} added.`
        }
    }

    const renderSuggestions = () => {
        const query = normalise(input.value)

        const selectedSlugs = new Set(
            chips.getValues()
                .map(value => findOption(value)?.slug)
                .filter(Boolean)
        )

        if (!query) {
            // No search term: show every feature that hasn't been selected.
            matches = options.filter(
                option => !selectedSlugs.has(option.slug)
            )
        } else {
            // Search term entered: show the six closest matches.
            matches = options
                .map((option, index) => ({
                    option,
                    index,
                    score: scoreMatch(
                        normalise(option.name),
                        query
                    )
                }))
                .filter(item =>
                    Number.isFinite(item.score) &&
                    !selectedSlugs.has(item.option.slug)
                )
                .sort((a, b) =>
                    a.score - b.score || a.index - b.index
                )
                .slice(0, 6)
                .map(item => item.option)
        }

        activeIndex = -1
        suggestions.replaceChildren()

        if (!matches.length) {
            const empty = document.createElement('div')
            empty.className = 'chip-suggestions-empty'
            empty.textContent = 'No matching features.'

            suggestions.append(empty)
        } else {
            matches.forEach((option, index) => {
                const button = document.createElement('button')

                button.type = 'button'
                button.className = 'chip-suggestion'
                button.id = `featureSuggestion-${index}`
                button.setAttribute('role', 'option')
                button.setAttribute('aria-selected', 'false')
                button.textContent = option.name

                button.addEventListener('mousedown', event => {
                    event.preventDefault()
                })

                button.addEventListener('mouseenter', () => {
                    activeIndex = index
                    updateActiveSuggestion()
                })

                button.addEventListener('click', () => {
                    selectFeature(option)
                })

                suggestions.append(button)
            })
        }

        suggestions.hidden = false
        input.setAttribute('aria-expanded', 'true')

        if (status) {
            status.textContent = matches.length
                ? `${matches.length} available features.`
                : 'No matching features.'
        }
    }

    input.addEventListener('input', renderSuggestions)
    input.addEventListener('focus', renderSuggestions)

    input.addEventListener('blur', event => {
        if (!suggestions.contains(event.relatedTarget)) {
            hideSuggestions()
        }
    })

    // Prevent Bootstrap's paste handler from creating free-form chips.
    input.addEventListener('paste', event => {
        event.stopImmediatePropagation()
    }, true)

    // Keyboard interaction.
    input.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault()
            event.stopImmediatePropagation()

            const option = matches[activeIndex] || matches[0]

            if (option) {
                selectFeature(option)
            } else if (status) {
                status.textContent =
                    'Choose an existing feature from the suggestions.'
            }

            return
        }

        if (
            !suggestions.hidden &&
            matches.length &&
            event.key === 'ArrowDown'
        ) {
            event.preventDefault()
            event.stopImmediatePropagation()

            activeIndex = activeIndex < matches.length - 1
                ? activeIndex + 1
                : 0

            updateActiveSuggestion()
            return
        }

        if (
            !suggestions.hidden &&
            matches.length &&
            event.key === 'ArrowUp'
        ) {
            event.preventDefault()
            event.stopImmediatePropagation()

            activeIndex = activeIndex > 0
                ? activeIndex - 1
                : matches.length - 1

            updateActiveSuggestion()
            return
        }

        if (event.key === 'Escape' && !suggestions.hidden) {
            event.preventDefault()
            event.stopImmediatePropagation()
            hideSuggestions()
        }
    }, true)

    // Synchronise any chips initially rendered from the query string.
    syncHiddenFields()
}

const initShareButton = () => {
    const button = document.querySelector('[data-share-url]')
    const status = document.getElementById('shareStatus')

    if (!button) return

    button.addEventListener('click', async () => {
        try {
            await copyToClipboard(window.location.href)

            if (status) {
                status.textContent = 'Page URL copied to clipboard!'
            }
        } catch (error) {
            if (status) {
                status.textContent =
                    'Unable to copy URL. Please copy it from your address bar.'
            }

            console.error('Share button error:', error)
        }
    })
}


onReady(() => {
    initBase()
    initFeaturePicker()

    bindRange('ratingRange', 'ratingOut', (v) => Number(v).toFixed(1))
    initMapSync()
    initOpenDatepicker()
    initShareButton()
})

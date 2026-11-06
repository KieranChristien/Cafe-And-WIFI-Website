/*!
 * Locale — Bootstrap 6 directory template
 */

import {Datepicker} from 'bootstrap'
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
    bindRange('ratingRange', 'ratingOut', (v) => Number(v).toFixed(1))
    initMapSync()
    initOpenDatepicker()
    initShareButton()
})

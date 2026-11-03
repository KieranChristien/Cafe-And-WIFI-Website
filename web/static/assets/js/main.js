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

        const input = instance._positionElement || instance._element
        const dialog = instance._element.closest('dialog[open]')
        const popup = instance._calendar?.context?.mainElement

        if (!dialog || !popup) return

        if (popup.parentElement !== dialog) {
            dialog.append(popup)
        }

        const inputRect = input.getBoundingClientRect()
        const dialogRect = dialog.getBoundingClientRect()

        popup.style.left =
            `${inputRect.left - dialogRect.left - dialog.clientLeft}px`

        popup.style.top =
            `${inputRect.bottom - dialogRect.top - dialog.clientTop}px`
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
            originalOnShow?.(...callbackArgs)

            const dialog = this._element.closest('dialog[open]')

            if (!dialog) return

            positionPopup(this)
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

const initOpenDatepicker = () => {
    const input = document.getElementById('openDate')

    if (!input) return

    const picker = Datepicker.getOrCreateInstance(input, {
        vcpOptions: {
            openOnFocus: false
        }
    })

    // Prevent Vanilla Calendar Pro from handling the input click.
    // Bootstrap will handle opening the calendar instead.
    input.addEventListener('click', (event) => {
        event.stopImmediatePropagation()
        picker.show()
    }, true)

    const clearButton = document.getElementById('clearOpenDate')

    if (clearButton) {
        const syncClearButton = () => {
            clearButton.hidden = !input.value.trim()
        }

        // Update when Bootstrap reports a selected date.
        input.addEventListener('change.bs.datepicker', syncClearButton)

        // Handle an initially populated input.
        syncClearButton()

        clearButton.addEventListener('click', (event) => {
            event.preventDefault()
            event.stopPropagation()

            picker.hide()
            picker.setSelectedDates([])

            // Notify other code that the date has changed.
            input.dispatchEvent(new Event('input', {bubbles: true}))
            input.dispatchEvent(new Event('change', {bubbles: true}))

            syncClearButton()
        })
    }
}

onReady(() => {
    initBase()
    bindRange('ratingRange', 'ratingOut', (v) => Number(v).toFixed(1))
    initMapSync()
    initOpenDatepicker()
})

/*!
 * Locale — Bootstrap 6 directory template
 */

import {Chips, Datepicker, Range} from 'bootstrap'
import {initBase, initYear, onReady} from './base.js'
import {initFormValidation} from './form-validation.js'

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

        bindCalendarTabExit(instance, popup, input, dialog)

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

    const bindCalendarTabExit = (instance, popup, input, dialog) => {
        if (instance.__dialogTabHandler?.popup === popup) return

        // Remove a handler from an earlier popup, if one exists.
        if (instance.__dialogTabHandler) {
            const {popup: oldPopup, handler} = instance.__dialogTabHandler
            oldPopup.removeEventListener('keydown', handler)
        }

        const getTabStops = () => {
            const selector = [
                'a[href]',
                'button',
                'input',
                'select',
                'textarea',
                '[tabindex]'
            ].join(',')

            return [...popup.querySelectorAll(selector)].filter(element =>
                element.tabIndex >= 0 &&
                !element.hasAttribute('disabled') &&
                element.getAttribute('aria-disabled') !== 'true' &&
                element.getAttribute('aria-hidden') !== 'true' &&
                element.getClientRects().length > 0
            )
        }

        const handler = event => {
            if (event.key !== 'Tab') return

            const tabStops = getTabStops()
            if (!tabStops.length) return

            const first = tabStops[0]
            const last = tabStops[tabStops.length - 1]
            const active = document.activeElement

            // Reverse Tab from the first calendar control returns to the date field.
            if (event.shiftKey && active === first) {
                event.preventDefault()
                instance.hide()
                input.focus()
                return
            }

            // Forward Tab from the last calendar control continues through the form.
            if (!event.shiftKey && active === last) {
                const clearButton = dialog.querySelector('#clearOpenDate')
                const openNowInput = dialog.querySelector('#openNow')

                const next = clearButton && !clearButton.hidden
                    ? clearButton
                    : openNowInput

                if (!next) return

                event.preventDefault()
                instance.hide()
                next.focus()
            }
        }

        popup.addEventListener('keydown', handler)

        instance.__dialogTabHandler = {
            popup,
            handler
        }
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

        const tabHandler = this.__dialogTabHandler

        if (tabHandler) {
            tabHandler.popup.removeEventListener('keydown', tabHandler.handler)
            this.__dialogTabHandler = null
        }

        return originalDispose.apply(this, args)
    }

    prototype.__dialogLayerPatched = true
}

initDatepickerDialogFix()

const bindRange = (rangeId, outId, format, zeroLabel = null) => {
    const range = document.getElementById(rangeId)
    const out = document.getElementById(outId)
    if (!range || !out) return

    const sync = () => {
        const value = Number(range.value);

        out.textContent = value === 0 && zeroLabel !== null
            ? zeroLabel
            : format(value);
    }
    range.addEventListener('input', sync)
    sync()
}

const setInlineStatus = (element, state, message) => {
    if (!element) return

    element.dataset.state = state
    element.textContent = message
    element.hidden = !message
}

/* ---------------------------------------------------------------
   Shared Leaflet map-pin icon
   --------------------------------------------------------------- */

const createMapPinIcon = ({
                              label = '',
                              active = false,
                              cafeId = null,
                          } = {}) => {

    const pin = document.createElement('span')

    pin.className = `map-pin${active ? ' is-active' : ''}`
    pin.textContent = String(label)

    if (cafeId !== null) {
        pin.dataset.cafeId = String(cafeId)
    }

    return L.divIcon({
        className: 'map-marker-wrapper',
        html: pin,
        iconSize: [28, 28],
        iconAnchor: [0, 28],
    })
}

/* ---------------------------------------------------------------
   Individual café location map
   --------------------------------------------------------------- */

const initListingMap = () => {
    const mapElement = document.getElementById('listingMap')

    if (!mapElement) return

    if (!window.L) {
        console.error('Leaflet is not available.')
        return
    }

    const latitude = Number(mapElement.dataset.latitude)
    const longitude = Number(mapElement.dataset.longitude)

    // Validate coordinates before passing them to Leaflet.
    const validCoordinates =
        Number.isFinite(latitude) &&
        Number.isFinite(longitude) &&
        latitude >= -90 &&
        latitude <= 90 &&
        longitude >= -180 &&
        longitude <= 180

    if (!validCoordinates) {
        console.error('Invalid café map coordinates.')
        return
    }

    // Initialise the map.
    const map = L.map(mapElement, {
        zoomControl: true,

        // Prevent the map from capturing normal page scrolling.
        scrollWheelZoom: false,

        // Allow users to explore the location.
        dragging: true,
        touchZoom: true,
        doubleClickZoom: true,
        keyboard: true,

        // Restrict maximum zoom to the available tile level.
        maxZoom: 19,
    })

    map.setView(
        [latitude, longitude],
        18
    )

    // OpenStreetMap tile layer.
    L.tileLayer(
        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors',
        }
    ).addTo(map)

    // Create the café marker.
    const marker = L.marker(
        [latitude, longitude],
        {
            icon: createMapPinIcon({
                label: '1',
                active: false,
            }),
        }
    ).addTo(map)

    // Use textContent so the café name is treated as text, not HTML.
    const popupContent = document.createElement('span')

    popupContent.textContent =
        mapElement.dataset.title || 'Café location'

    marker.bindPopup(popupContent)

    // Ensure Leaflet calculates the correct dimensions.
    requestAnimationFrame(() => {
        map.invalidateSize()
    })
}

const initListingPhotoLightbox = () => {
    const dialog = document.getElementById("listingPhotoLightbox");

    const triggers = Array.from(
        document.querySelectorAll("[data-listing-gallery-image]")
    );

    if (!dialog || !triggers.length) return;

    const image = dialog.querySelector("#listingPhotoLightboxImage");
    const count = dialog.querySelector("#listingPhotoLightboxCount");
    const closeButton = dialog.querySelector("[data-lightbox-close]");
    const previousButton = dialog.querySelector("[data-lightbox-previous]");
    const nextButton = dialog.querySelector("[data-lightbox-next]");

    if (!image || !count || !closeButton || !previousButton || !nextButton) {
        return;
    }

    let activeIndex = 0;
    let opener = null;

    function showImage(index) {
        activeIndex = (index + triggers.length) % triggers.length;

        const trigger = triggers[activeIndex];
        const thumbnail = trigger.querySelector("img");

        image.src = trigger.href;
        image.alt = thumbnail?.alt || ("Photo " + (activeIndex + 1));

        count.textContent =
            (activeIndex + 1) + " / " + triggers.length;
    }

    function openViewer(trigger, index) {
        opener = trigger;
        showImage(index);
        dialog.showModal();
    }

    triggers.forEach((trigger, index) => {
        trigger.addEventListener("click", event => {
            event.preventDefault();
            openViewer(trigger, index);
        });
    });

    previousButton.hidden = triggers.length < 2;
    nextButton.hidden = triggers.length < 2;

    closeButton.addEventListener("click", () => {
        dialog.close();
    });

    previousButton.addEventListener("click", () => {
        showImage(activeIndex - 1);
    });

    nextButton.addEventListener("click", () => {
        showImage(activeIndex + 1);
    });

    document.addEventListener("keydown", event => {
        if (!dialog.open || triggers.length < 2) return;

        if (event.key === "ArrowLeft") {
            event.preventDefault();
            showImage(activeIndex - 1);
        }

        if (event.key === "ArrowRight") {
            event.preventDefault();
            showImage(activeIndex + 1);
        }
    });

    // Clicking the backdrop closes the viewer.
    dialog.addEventListener("click", event => {
        if (event.target === dialog) {
            dialog.close();
        }
    });

    // Restore focus to the thumbnail that opened the viewer.
    dialog.addEventListener("close", () => {
        image.removeAttribute("src");

        if (opener) {
            opener.focus();
            opener = null;
        }
    });
};

const activateMapCafe = (cafeId) => {
    const selectedId = String(cafeId)

    // Highlight the corresponding map pin.
    document.querySelectorAll(
        '.map-pin[data-cafe-id]'
    ).forEach((pin) => {
        pin.classList.toggle(
            'is-active',
            pin.dataset.cafeId === selectedId
        )
    })

    // Highlight the corresponding listing.
    document.querySelectorAll(
        '.listing[data-cafe-id]'
    ).forEach((listing) => {
        listing.classList.toggle(
            'is-map-active',
            listing.dataset.cafeId === selectedId
        )
    })
}

/* ---------------------------------------------------------------
   Highlight the map pin associated with a listing
   --------------------------------------------------------------- */

const initMapSync = () => {
    const listings = document.querySelectorAll(
        '.listing[data-cafe-id]'
    )

    if (!listings.length) return

    // Hovering or focusing a listing activates its map pin.
    listings.forEach((listing) => {
        const activate = () => {
            activateMapCafe(listing.dataset.cafeId)
        }

        listing.addEventListener('mouseenter', activate)
        listing.addEventListener('focusin', activate)
    })

    // Initially activate the first map pin.
    const firstPin = document.querySelector(
        '.map-pin[data-cafe-id]'
    )

    if (firstPin) {
        activateMapCafe(firstPin.dataset.cafeId)
    }
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

    const openNowInput = document.getElementById('openNow')
    const dateControl = document.getElementById('openDateControl')
    const clearButton = document.getElementById('clearOpenDate')

    // Capture the server-provided date before initialising Bootstrap.
    const initialValue = input.value.trim()
    const initialDate = parseInitialDate(initialValue)

    // Prevent Bootstrap from prematurely parsing the input.
    input.value = ''

    const picker = Datepicker.getOrCreateInstance(input, {
        locale: 'en-GB',
        positionElement: input,
        selectedDates: initialDate ? [initialDate] : [],

        vcpOptions: {
            openOnFocus: false
        }
    })

    // Preserve an unrecognised value.
    if (!initialDate && initialValue) {
        input.value = initialValue
    }

    // --------------------------------------------------
    // Clear button
    // --------------------------------------------------

    const syncClearButton = () => {
        if (!clearButton) return

        clearButton.hidden =
            input.disabled || !input.value.trim()
    }

    if (clearButton) {

        input.addEventListener(
            'change.bs.datepicker',
            syncClearButton
        )

        clearButton.addEventListener('click', (event) => {
            event.preventDefault()
            event.stopPropagation()

            picker.hide()
            picker.setSelectedDates([])
            input.value = ''

            input.dispatchEvent(
                new Event('input', {bubbles: true})
            )

            input.dispatchEvent(
                new Event('change', {bubbles: true})
            )

            syncClearButton()
        })
    }

    // --------------------------------------------------
    // Open now toggle
    // --------------------------------------------------

    const syncOpenNow = () => {

        const openNow = openNowInput?.checked ?? false

        if (openNow) {

            // Close the calendar if it is currently open.
            picker.hide()

            // Clear the selected date from the datepicker.
            picker.setSelectedDates([])

            // Clear the actual input value.
            input.value = ''

            input.blur()

        }

        // Disable or enable the date selector.
        input.disabled = openNow

        // Update accessibility state.
        input.setAttribute('aria-disabled', String(openNow))

        // Update accessibility state.
        input.setAttribute('aria-disabled', String(openNow))

        // Update the visual disabled state.
        dateControl?.classList.toggle(
            'is-disabled',
            openNow
        )

        // Hide or show the clear button.
        syncClearButton()

    }

    if (openNowInput) {

        openNowInput.addEventListener(
            'change',
            syncOpenNow
        )

        // Initialise the correct state on page load.
        syncOpenNow()

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

    picker.addEventListener('focusout', event => {

        // Keep suggestions open while focus remains inside
        // the feature picker.
        if (
            event.relatedTarget &&
            picker.contains(event.relatedTarget)
        ) {
            return
        }

        // Focus has moved outside the feature picker.
        hideSuggestions()

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

const initLocationPicker = () => {

    const addressForm = document.getElementById(
        'addressForm'
    )

    const mapContainer = document.getElementById(
        'locationMapContainer'
    )

    const mapElement = document.getElementById(
        'locationMap'
    )

    const status = document.getElementById(
        'addressSearchStatus'
    )

    const button = document.getElementById(
        'findAddressButton'
    )

    const latitudeInput = document.getElementById(
        'latitude'
    )

    const longitudeInput = document.getElementById(
        'longitude'
    )

    const coordinatesOutput = document.getElementById(
        'selectedCoordinates'
    )

    const addressInput = document.getElementById('cAddress')
    const addressQueryInput = document.getElementById('addressQuery')

    const mapCenterLatitudeInput = document.getElementById(
        'mapCenterLatitude'
    )

    const mapCenterLongitudeInput = document.getElementById(
        'mapCenterLongitude'
    )

    const mapZoomInput = document.getElementById('mapZoom')

    const editForm = document.getElementById('editForm')

    const timezoneInput = document.getElementById('timezone')

    const timezoneStatus = document.getElementById('timezoneStatus')

    const timezonePreviewUrl =
        editForm?.dataset.timezonePreviewUrl

    let timezoneController = null
    let timezoneRequestId = 0


    const lookupTimezone = async (latlng) => {

        if (
            !timezoneInput ||
            !timezonePreviewUrl
        ) {
            return
        }

        // Cancel any previous lookup.
        timezoneController?.abort()

        const controller = new AbortController()

        timezoneController = controller

        const requestId = ++timezoneRequestId

        const csrfToken = editForm.querySelector(
            'input[name="csrf_token"]'
        )?.value

        timezoneInput.value = ''

        setInlineStatus(
            timezoneStatus,
            'loading',
            'Detecting time zone...'
        )

        try {

            const response = await fetch(
                timezonePreviewUrl,
                {
                    method: 'POST',

                    headers: {
                        'Accept': 'application/json',
                        'Content-Type':
                            'application/x-www-form-urlencoded;charset=UTF-8',

                        ...(csrfToken
                            ? {'X-CSRFToken': csrfToken}
                            : {}),
                    },

                    body: new URLSearchParams({
                        latitude: latlng.lat.toFixed(7),
                        longitude: latlng.lng.toFixed(7),
                    }),

                    signal: controller.signal,
                }
            )

            const result = await response.json()

            if (!response.ok) {
                throw new Error(
                    result.error || 'Unable to determine time zone.'
                )
            }

            // Ignore outdated responses.
            if (requestId !== timezoneRequestId) {
                return
            }

            timezoneInput.value = result.timezone

            timezoneInput.dispatchEvent(
                new Event('change', {bubbles: true})
            )

            setInlineStatus(
                timezoneStatus,
                'success',
                'Time zone automatically detected from the map location.'
            )

        } catch (error) {

            if (error.name === 'AbortError') {
                return
            }

            if (requestId !== timezoneRequestId) {
                return
            }

            setInlineStatus(
                timezoneStatus,
                'error',
                error.message
            )

        }

    }

    if (
        !addressForm ||
        !mapContainer ||
        !mapElement
    ) {
        return
    }

    let map = null
    let marker = null

    // --------------------------------------------------
    // Update the selected coordinates
    // --------------------------------------------------

    const updateCoordinates = (latlng) => {

        latitudeInput.value = latlng.lat.toFixed(7)

        longitudeInput.value = latlng.lng.toFixed(7)

        coordinatesOutput.textContent =
            `Latitude: ${latitudeInput.value}, ` +
            `Longitude: ${longitudeInput.value}`

        lookupTimezone(latlng)
    }

    // --------------------------------------------------
    // Preserve the visible map centre and zoom
    // --------------------------------------------------

    const updateMapView = () => {
        if (!map) return

        const center = map.getCenter()

        mapCenterLatitudeInput.value = center.lat.toFixed(7)
        mapCenterLongitudeInput.value = center.lng.toFixed(7)
        mapZoomInput.value = String(map.getZoom())
    }


    // --------------------------------------------------
    // Create or restore the map
    // --------------------------------------------------

    const initialiseMap = (
        latitude,
        longitude,
        viewState = {}
    ) => {

        mapContainer.hidden = false

        const centerLatitude =
            Number.isFinite(viewState.centerLatitude)
                ? viewState.centerLatitude
                : latitude

        const centerLongitude =
            Number.isFinite(viewState.centerLongitude)
                ? viewState.centerLongitude
                : longitude

        const zoom =
            Number.isInteger(viewState.zoom) &&
            viewState.zoom >= 0 &&
            viewState.zoom <= 19
                ? viewState.zoom
                : 18

        if (!map) {

            map = L.map(mapElement).setView(
                [centerLatitude, centerLongitude],
                zoom
            )

            L.tileLayer(
                'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                {
                    maxZoom: 19,
                    attribution:
                        '&copy; OpenStreetMap contributors'
                }
            ).addTo(map)

            // Keep the hidden viewport fields up to date.
            map.on('moveend zoomend', updateMapView)

            // Clicking the map moves the marker.
            map.on('click', (event) => {

                if (marker) {
                    marker.setLatLng(event.latlng)
                } else {
                    marker = L.marker(
                        event.latlng,
                        {
                            icon: createMapPinIcon({
                                label: '1',
                                active: false,
                            }),
                            draggable: true,
                        }
                    ).addTo(map)

                    marker.on('dragend', () => {
                        updateCoordinates(marker.getLatLng())
                    })
                }

                updateCoordinates(event.latlng)

            })

        } else {

            map.setView(
                [centerLatitude, centerLongitude],
                zoom
            )

        }

        // Leaflet must recalculate its size after the
        // previously hidden container becomes visible.
        requestAnimationFrame(() => {
            map.invalidateSize()
            updateMapView()
        })

        // Restore the marker independently of the map centre.
        const markerPosition = L.latLng(
            latitude,
            longitude
        )

        if (marker) {
            marker.setLatLng(markerPosition)
        } else {
            marker = L.marker(
                markerPosition,
                {
                    icon: createMapPinIcon({
                        label: '1',
                        active: false,
                    }),
                    draggable: true,
                }
            ).addTo(map)

            marker.on('dragend', () => {
                updateCoordinates(marker.getLatLng())
            })
        }

        updateCoordinates(markerPosition)
    }

    // --------------------------------------------------
    // Keep the rough address in the main form
    // --------------------------------------------------

    addressInput?.addEventListener('input', () => {

        addressQueryInput.value = addressInput.value

        // The previous selection may no longer match the new address.
        latitudeInput.value = ''
        longitudeInput.value = ''

        timezoneController?.abort()
        timezoneRequestId++

        timezoneInput.value = ''

        setInlineStatus(
            timezoneStatus,
            '',
            ''
        )
        setInlineStatus(
            status,
            'info',
            'Search for the updated address to select its location.'
        )

        mapCenterLatitudeInput.value = ''
        mapCenterLongitudeInput.value = ''
        mapZoomInput.value = '18'

        mapContainer.hidden = true
    })


    // --------------------------------------------------
    // Address form submission
    // --------------------------------------------------

    addressForm.addEventListener('submit', async (event) => {

        event.preventDefault()

        addressQueryInput.value = addressInput.value

        if (!addressForm.reportValidity()) {
            return
        }

        setInlineStatus(
            status,
            'loading',
            'Searching for location...'
        )

        button.disabled = true

        try {

            const response = await fetch(
                addressForm.action,
                {
                    method: 'POST',
                    body: new FormData(addressForm),
                    headers: {
                        'Accept': 'application/json'
                    }
                }
            )

            const result = await response.json()

            if (!response.ok) {
                throw new Error(
                    result.error || 'Unable to find location.'
                )
            }

            initialiseMap(
                result.latitude,
                result.longitude
            )

            setInlineStatus(
                status,
                'success',
                'Location found. Adjust the marker to the café entrance.'
            )

        } catch (error) {

            setInlineStatus(
                status,
                'error',
                error.message
            )

        } finally {

            button.disabled = false

        }

    })


    // --------------------------------------------------
    // Use the user's current location (optional)
    // --------------------------------------------------

    const locateButton = document.getElementById(
        'locateMeButton'
    )

    locateButton?.addEventListener('click', () => {

        if (!navigator.geolocation) {
            status.textContent =
                'Geolocation is not supported by your browser.'
            return
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {

                initialiseMap(
                    position.coords.latitude,
                    position.coords.longitude
                )

                status.textContent =
                    'Current location selected.'

            },
            () => {

                status.textContent =
                    'Unable to retrieve your location.'

            }
        )

    })

    // --------------------------------------------------
    // Restore a previous map selection after form errors
    // --------------------------------------------------

    const initialLatitudeText = latitudeInput.value.trim()
    const initialLongitudeText = longitudeInput.value.trim()

    if (initialLatitudeText && initialLongitudeText) {

        const latitude = Number(initialLatitudeText)
        const longitude = Number(initialLongitudeText)

        const validCoordinates =
            Number.isFinite(latitude) &&
            Number.isFinite(longitude) &&
            latitude >= -90 &&
            latitude <= 90 &&
            longitude >= -180 &&
            longitude <= 180

        if (validCoordinates) {

            const savedCenterLatitude = Number(
                mapCenterLatitudeInput.value
            )

            const savedCenterLongitude = Number(
                mapCenterLongitudeInput.value
            )

            const validCenter =
                mapCenterLatitudeInput.value.trim() !== '' &&
                mapCenterLongitudeInput.value.trim() !== '' &&
                Number.isFinite(savedCenterLatitude) &&
                Number.isFinite(savedCenterLongitude) &&
                savedCenterLatitude >= -90 &&
                savedCenterLatitude <= 90 &&
                savedCenterLongitude >= -180 &&
                savedCenterLongitude <= 180

            const savedZoom = Number(mapZoomInput.value)

            initialiseMap(
                latitude,
                longitude,
                {
                    centerLatitude: validCenter
                        ? savedCenterLatitude
                        : latitude,

                    centerLongitude: validCenter
                        ? savedCenterLongitude
                        : longitude,

                    zoom: Number.isInteger(savedZoom) &&
                    savedZoom >= 0 &&
                    savedZoom <= 19
                        ? savedZoom
                        : 18
                }
            )

            status.textContent =
                'Your previous map selection has been restored. ' +
                'You can adjust the marker if necessary.'
        }
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


/* ---------------------------------------------------------------
   Results map
   --------------------------------------------------------------- */

const initResultsMap = () => {
    const mapElement = document.getElementById('resultsMap')
    const locationsElement = document.getElementById('mapLocations')

    if (!mapElement || !locationsElement) return

    if (!window.L) {
        console.error('Leaflet is not available.')
        return
    }

    let locations

    try {
        locations = JSON.parse(locationsElement.textContent)
    } catch (error) {
        console.error('Unable to read map locations:', error)
        return
    }

    if (!Array.isArray(locations)) {
        console.error('Invalid map locations.')
        return
    }

    // Validate every location before adding it to the map.
    const validLocations = locations.filter((location) => {
        const latitude = Number(location.latitude)
        const longitude = Number(location.longitude)

        return (
            Number.isSafeInteger(Number(location.id)) &&
            Number.isFinite(latitude) &&
            Number.isFinite(longitude) &&
            latitude >= -90 &&
            latitude <= 90 &&
            longitude >= -180 &&
            longitude <= 180
        )
    })

    if (!validLocations.length) return

    // Create the map.
    const map = L.map(mapElement, {
        zoomControl: true,
        scrollWheelZoom: false,
        dragging: true,
        touchZoom: true,
        doubleClickZoom: true,
        keyboard: true,
        maxZoom: 19,
    })

    // Add OpenStreetMap tiles.
    L.tileLayer(
        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors',
        }
    ).addTo(map)

    const mapPoints = []

    // Add one marker for each café.
    // Add one marker for each café.
    validLocations.forEach((location, index) => {

        const latitude = Number(location.latitude)
        const longitude = Number(location.longitude)
        const cafeId = String(location.id)

        const position = L.latLng(
            latitude,
            longitude
        )

        mapPoints.push(position)

        const marker = L.marker(
            position,
            {
                icon: createMapPinIcon({
                    label: index + 1,
                    cafeId: cafeId,
                    active: index === 0,
                }),
            }
        ).addTo(map)

        // Synchronise the listing when interacting with its marker.
        marker.on('mouseover', () => {
            activateMapCafe(cafeId)
        })

        marker.on('click', () => {
            activateMapCafe(cafeId)
        })

// Support keyboard navigation.
        marker.getElement()?.addEventListener('focus', () => {
            activateMapCafe(cafeId)
        })

        // Safely display the café name in the popup.
        const popup = document.createElement('span')
        popup.textContent = location.name

        marker.bindPopup(popup)
    })

    // --------------------------------------------------
    // Fit all markers inside the visible map area.
    // --------------------------------------------------

    const fitMapToMarkers = () => {
        map.invalidateSize({pan: false})

        const mapSize = map.getSize()

        // Don't attempt to fit the map while it has no dimensions.
        // This can happen when the responsive sidebar is hidden.
        if (!mapSize.x || !mapSize.y) return

        if (mapPoints.length === 1) {
            // A single location needs a useful local view.
            map.setView(mapPoints[0], 15, {
                animate: false,
            })

            return
        }

        const bounds = L.latLngBounds(mapPoints)

        map.fitBounds(
            bounds,
            {
                paddingTopLeft: [40, 40],
                paddingBottomRight: [40, 40],
                maxZoom: 15,
                animate: false,
            }
        )
    }

    // Initialise once the map has dimensions.
    // ResizeObserver also handles the map becoming visible
    // when a user resizes from mobile to desktop.
    if (
        mapElement.clientWidth > 0 &&
        mapElement.clientHeight > 0
    ) {
        requestAnimationFrame(fitMapToMarkers)
    } else {
        const resizeObserver = new ResizeObserver(() => {
            if (
                mapElement.clientWidth > 0 &&
                mapElement.clientHeight > 0
            ) {
                resizeObserver.disconnect()

                requestAnimationFrame(fitMapToMarkers)
            }
        })

        resizeObserver.observe(mapElement)
    }
}


const initNearestSort = () => {
    const link = document.querySelector('[data-nearest-sort]')
    const status = document.getElementById('nearestSortStatus')

    if (!link) return

    link.addEventListener('click', event => {
        event.preventDefault()

        if (!navigator.geolocation) {
            if (status) {
                status.textContent =
                    'Geolocation is not supported by your browser.'
            }
            return
        }

        if (link.dataset.locating === 'true') return

        link.dataset.locating = 'true'

        if (status) {
            status.textContent = 'Getting your location…'
        }

        navigator.geolocation.getCurrentPosition(
            position => {
                const url = new URL(
                    link.href,
                    window.location.href
                )

                url.searchParams.set(
                    'user_latitude',
                    position.coords.latitude.toFixed(5)
                )

                url.searchParams.set(
                    'user_longitude',
                    position.coords.longitude.toFixed(5)
                )

                url.hash = 'results'

                window.location.assign(url.href)
            },

            error => {
                delete link.dataset.locating

                if (!status) return

                const messages = {
                    1: 'Location permission denied.',
                    2: 'Your location is unavailable.',
                    3: 'Location request timed out.'
                }

                status.textContent =
                    messages[error.code] ||
                    'Unable to retrieve your location.'
            },

            {
                enableHighAccuracy: false,
                maximumAge: 300000,
                timeout: 10000
            }
        )
    })
}

const initManualClosure = () => {

    const checkbox = document.getElementById('isManuallyClosed')
    const messageContainer = document.getElementById('manualClosedMessageField')
    const messageSelect = document.getElementById('cClosedMessage')
    const fieldset = document.getElementById('openingHoursFieldset')

    if (!checkbox || !messageContainer || !messageSelect || !fieldset) return

    const sync = () => {

        const manuallyClosed = checkbox.checked

        // Closure reason
        messageContainer.hidden = !manuallyClosed
        messageSelect.disabled = !manuallyClosed
        messageSelect.required = manuallyClosed

        // Regular opening hours
        fieldset.disabled = manuallyClosed
        fieldset.hidden = manuallyClosed

    }

    checkbox.addEventListener('change', sync)

    // Apply the saved state when the page loads.
    sync()

}

const initOpeningHours = () => {

    const container = document.getElementById('openingHours')

    if (!container) return

    container.querySelectorAll('[data-opening-hours-row]').forEach(row => {

        const closedInput = row.querySelector('input[type="checkbox"]')

        const timeInputs = row.querySelectorAll('input[type="time"]')

        if (!closedInput) return

        const sync = () => {

            const closed = closedInput.checked

            row.classList.toggle('is-closed', closed)

            timeInputs.forEach(input => {

                input.disabled = closed
                input.required = !closed

                if (closed) {
                    input.value = ''
                }

            })

        }

        closedInput.addEventListener('change', sync)

        sync()

    })

}

function initOverviewEditor() {
    const overviewSource = document.getElementById("overviewSource");
    const overviewElement = document.getElementById("overviewEditor");

    // Make sure both elements exist and the editor hasn't already been initialized.
    if (
        !overviewSource ||
        !overviewElement ||
        overviewElement.dataset.quillInitialized === "true"
    ) {
        return;
    }

    // Import dialog elements.
    const importDialog = document.getElementById("overviewImportDialog");
    const importSource = document.getElementById("overviewImportSource");
    const previewButton = document.getElementById("overviewImportPreview");
    const previewArea = document.getElementById("overviewImportPreviewArea");
    const previewContent = document.getElementById("overviewImportPreviewContent");
    const confirmButton = document.getElementById("overviewImportConfirm");

    let importedDelta = null;
    let previewQuill = null;

    // Create the Quill editor.
    overviewElement.hidden = false;

    const quill = new Quill(overviewElement, {
        theme: "snow",

        formats: [
            "header",
            "bold",
            "italic",
            "underline",
            "strike",
            "list",
            "indent",
            "blockquote",
            "link"
        ],

        modules: {
            toolbar: {
                container: [
                    [{header: [2, 3, false]}],
                    ["bold", "italic", "underline", "strike"],
                    [{list: "ordered"}, {list: "bullet"}],
                    ["blockquote", "link"],
                    ["clean"],
                    ["importHtml"]
                ],

                handlers: {
                    importHtml: function () {
                        if (importDialog && !importDialog.open) {
                            importDialog.showModal();
                        }
                    }
                }
            },

            history: {
                delay: 1000,
                maxStack: 100,
                userOnly: true
            }
        }
    });

    quill.root.classList.add("prose")

    quill.root.setAttribute(
        "aria-labelledby",
        "overviewEditorLabel"
    );

    overviewElement.dataset.quillInitialized = "true";

    // Hide the original WTForms textarea.
    overviewSource.hidden = true;

    // Give the custom import button an icon and tooltip.
    const importButton = quill
        .getModule("toolbar")
        .container
        .querySelector(".ql-importHtml");

    if (importButton) {
        importButton.innerHTML = `
            <svg
                viewBox="0 0 18 18"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
            >
                <path d="M9 12V3"></path>
                <path d="M5.5 6.5 9 3l3.5 3.5"></path>
                <path d="M3 11v4h12v-4"></path>
            </svg>
        `;

        importButton.type = "button";
        importButton.title = "Import HTML";
        importButton.setAttribute("aria-label", "Import HTML");
    }

    // Load existing HTML into the editor, if present.
    if (overviewSource.value.trim()) {
        const initialDelta = quill.clipboard.convert({
            html: overviewSource.value,
            text: ""
        });

        quill.setContents(initialDelta, "silent");
    }

    // Keep the original textarea synchronized with the editor.
    function syncOverviewSource() {
        overviewSource.value = quill.getSemanticHTML();
    }

    quill.on("text-change", syncOverviewSource);

    // Set up the HTML import dialog.
    if (
        importDialog &&
        importSource &&
        previewButton &&
        previewArea &&
        previewContent &&
        confirmButton
    ) {
        // Create a separate, read-only Quill editor for the preview.
        previewQuill = new Quill(previewContent, {
            theme: "snow",
            readOnly: true,
            modules: {
                toolbar: false
            }
        });

        previewQuill.root.classList.add("prose");

        previewQuill.enable(false);

        // Close dialog buttons.
        importDialog.querySelectorAll("[data-import-close]").forEach(button => {
            button.addEventListener("click", () => {
                importDialog.close();
            });
        });

        // Close the dialog when clicking its backdrop.
        importDialog.addEventListener("click", event => {
            if (event.target === importDialog) {
                importDialog.close();
            }
        });

        // Reset the preview whenever the HTML source changes.
        importSource.addEventListener("input", () => {
            importedDelta = null;
            confirmButton.disabled = true;
            previewArea.hidden = true;
        });

        // Convert and preview the supplied HTML.
        previewButton.addEventListener("click", () => {
            const html = importSource.value.trim();

            if (!html) {
                importedDelta = null;
                confirmButton.disabled = true;
                previewArea.hidden = true;
                return;
            }

            try {
                const delta = quill.clipboard.convert({
                    html: html,
                    text: ""
                });

                previewQuill.setContents(delta, "silent");

                importedDelta = delta;
                previewArea.hidden = false;
                confirmButton.disabled = false;

            } catch (error) {
                console.error("HTML import preview failed:", error);

                importedDelta = null;
                confirmButton.disabled = true;
                previewArea.hidden = true;
            }
        });

        // Import the previewed HTML into the main editor.
        confirmButton.addEventListener("click", () => {
            if (!importedDelta) {
                return;
            }

            quill.setContents(importedDelta, "user");

            syncOverviewSource();

            importDialog.close();

            // Clear the import dialog for the next use.
            importSource.value = "";
            importedDelta = null;
            confirmButton.disabled = true;
            previewArea.hidden = true;

            // Return focus to the main editor.
            quill.focus();
        });
    }

    // Make sure the latest HTML is submitted with the form.
    if (overviewSource.form) {
        overviewSource.form.addEventListener("submit", () => {
            syncOverviewSource();
        });
    }

    return quill;
}

// --------------------------------------------------
// Cover image editor
// --------------------------------------------------

function initCoverImageUpload() {
    const dropzone = document.getElementById("coverImageDropzone");
    const input = document.getElementById("coverImageInput");
    const preview = document.getElementById("coverPreview");
    const status = document.getElementById("coverImageStatus");

    const overlayTitle = document.getElementById("coverImageOverlayTitle");
    const overlayHint = document.getElementById("coverImageOverlayHint");

    if (!dropzone || !input || !preview || !status) return;

    const originalImage = preview.src;
    const maxSize = 5 * 1024 * 1024;

    const allowedTypes = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    ];

    let previewUrl = null;
    let dragDepth = 0;

    function setStatus(message, state = "success") {
        status.textContent = message;
        status.dataset.state = state;
        status.hidden = !message;
    }

    function revokePreview() {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            previewUrl = null;
        }
    }

    function resetPreview() {
        revokePreview();
        preview.src = originalImage;
    }

    function isValidFile(file) {
        if (!allowedTypes.includes(file.type)) {
            setStatus(
                "Please select a JPG, PNG, WebP or GIF image.",
                "error"
            );
            return false;
        }

        if (file.size > maxSize) {
            setStatus(
                "Your image must be 5 MB or smaller.",
                "error"
            );
            return false;
        }

        return true;
    }

    function showPreview(file) {
        revokePreview();

        previewUrl = URL.createObjectURL(file);
        preview.src = previewUrl;

        setStatus(
            `${file.name} selected. Save your changes to upload it.`,
            "success"
        );
    }

    function restoreDragText() {
        overlayTitle.textContent = "Change cover image";
        overlayHint.textContent = "Choose a file or drag it here";
    }

    function setDragging(active) {
        dropzone.classList.toggle("is-dragging", active);

        if (active) {
            overlayTitle.textContent = "Drop to upload";
            overlayHint.textContent = "Release to use this image";
        } else {
            restoreDragText();
        }
    }

    function isFileDrag(event) {
        return Array.from(event.dataTransfer?.types || []).includes("Files");
    }

    // Standard file picker
    input.addEventListener("change", () => {
        const file = input.files?.[0];

        if (!file) return;

        if (!isValidFile(file)) {
            input.value = "";
            resetPreview();
            return;
        }

        showPreview(file);
    });

    // Dragging a file over the cover
    dropzone.addEventListener("dragenter", (event) => {
        if (!isFileDrag(event)) return;

        event.preventDefault();
        dragDepth++;
        setDragging(true);
    });

    dropzone.addEventListener("dragover", (event) => {
        if (!isFileDrag(event)) return;

        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
        setDragging(true);
    });

    dropzone.addEventListener("dragleave", (event) => {
        if (!isFileDrag(event)) return;

        event.preventDefault();

        dragDepth = Math.max(0, dragDepth - 1);

        if (dragDepth === 0) {
            setDragging(false);
        }
    });

    // Dropping a file onto the cover
    dropzone.addEventListener("drop", (event) => {
        if (!isFileDrag(event)) return;

        event.preventDefault();

        dragDepth = 0;
        setDragging(false);

        const files = Array.from(event.dataTransfer.files || []);

        if (files.length !== 1) {
            setStatus("Please drop one image at a time.", "error");
            return;
        }

        const file = files[0];

        if (!isValidFile(file)) return;

        // Put the dropped file into the actual form field.
        // This ensures it is submitted with the rest of the form.
        try {
            const transfer = new DataTransfer();
            transfer.items.add(file);
            input.files = transfer.files;
        } catch {
            setStatus(
                "Drag and drop is unavailable in this browser. Click the image to choose a file.",
                "error"
            );
            return;
        }

        showPreview(file);
    });

    window.addEventListener("pagehide", revokePreview);
}


// --------------------------------------------------
// Café gallery photo uploads
// --------------------------------------------------

function initCafePhotoUpload() {
    const dropzone = document.getElementById("photosDropzone");
    const input = document.getElementById("photosInput");
    const grid = document.getElementById("photosGrid");
    const status = document.getElementById("photosStatus");
    const count = document.getElementById("photosCount");
    const emptyState = document.getElementById("photosEmptyState");

    const dropzoneTitle = document.getElementById("photosDropzoneTitle");
    const dropzoneHint = document.getElementById("photosDropzoneHint");

    if (!dropzone || !input || !grid) return;

    const maxPhotos = 20;
    const maxSize = 5 * 1024 * 1024;

    const existingCount = Number(grid.dataset.existingCount || 0);

    const allowedTypes = new Set([
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    ]);

    const allowedExtensions = new Set([
        "jpg",
        "jpeg",
        "png",
        "webp",
        "gif",
    ]);

    let selectedFiles = [];
    let previewUrls = [];
    let dragDepth = 0;

    function setStatus(message, state = "info") {
        if (!status) return;

        status.textContent = message;
        status.dataset.state = state;
        status.hidden = !message;
    }

    function getRemovalCheckboxes() {
        return Array.from(
            grid.querySelectorAll("[data-remove-photo]")
        );
    }

    function getRemovalCount() {
        return getRemovalCheckboxes()
            .filter(checkbox => checkbox.checked)
            .length;
    }

    function getRemainingSlots() {
        return maxPhotos - (
            existingCount -
            getRemovalCount() +
            selectedFiles.length
        );
    }

    function updateCount() {
        const total = (
            existingCount -
            getRemovalCount() +
            selectedFiles.length
        );

        if (count) {
            count.textContent = `${total} / ${maxPhotos} photos`;
        }

        if (emptyState) {
            emptyState.hidden = total > 0;
        }

        dropzone.classList.toggle(
            "is-full",
            getRemainingSlots() <= 0
        );
    }

    function revokePreviews() {
        previewUrls.forEach(url => URL.revokeObjectURL(url));
        previewUrls = [];
    }

    function syncInputFiles() {
        try {
            const transfer = new DataTransfer();

            selectedFiles.forEach(file => {
                transfer.items.add(file);
            });

            input.files = transfer.files;

            return true;

        } catch {
            setStatus(
                "Your browser could not prepare these files for upload.",
                "error"
            );

            return false;
        }
    }

    function isValidFile(file) {
        const extension = file.name
            .split(".")
            .pop()
            .toLowerCase();

        if (
            !allowedExtensions.has(extension) ||
            (file.type && !allowedTypes.has(file.type))
        ) {
            setStatus(
                "Only JPG, PNG, WebP and GIF images are supported.",
                "error"
            );

            return false;
        }

        if (!file.size || file.size > maxSize) {
            setStatus(
                "Each photo must be 5 MB or smaller.",
                "error"
            );

            return false;
        }

        return true;
    }

    function renderPendingPhotos() {
        revokePreviews();

        grid.querySelectorAll("[data-pending-photo]")
            .forEach(card => card.remove());

        selectedFiles.forEach((file, index) => {

            const card = document.createElement("figure");
            card.className = "cafe-photo-card cafe-photo-card--pending";
            card.dataset.pendingPhoto = "";

            const imageFrame = document.createElement("div");
            imageFrame.className = "cafe-photo-card__image";

            const image = document.createElement("img");

            const previewUrl = URL.createObjectURL(file);
            previewUrls.push(previewUrl);

            image.src = previewUrl;
            image.alt = file.name;

            imageFrame.appendChild(image);

            const caption = document.createElement("figcaption");
            caption.className = "cafe-photo-card__caption";

            const fileName = document.createElement("span");
            fileName.className = "cafe-photo-card__filename";
            fileName.textContent = file.name;

            const removeButton = document.createElement("button");

            removeButton.type = "button";
            removeButton.className = "cafe-photo-card__remove";
            removeButton.textContent = "Remove";

            removeButton.addEventListener("click", () => {
                selectedFiles.splice(index, 1);

                if (syncInputFiles()) {
                    renderPendingPhotos();
                    updateCount();

                    if (selectedFiles.length > 0) {
                        setStatus(
                            `${selectedFiles.length} new photo(s) selected. ` +
                            "Save your changes to upload them.",
                            "success"
                        );
                    } else {
                        setStatus("");
                    }
                }
            });

            caption.append(fileName, removeButton);

            card.append(imageFrame, caption);

            grid.appendChild(card);
        });
    }

    function updateRemovalAppearance() {
        getRemovalCheckboxes().forEach(checkbox => {

            const card = checkbox.closest(".cafe-photo-card");

            if (!card) return;

            card.classList.toggle(
                "is-marked-for-removal",
                checkbox.checked
            );

        });

        updateCount();
    }

    function addFiles(files) {
        const incoming = Array.from(files || []);

        if (!incoming.length) return;

        const validFiles = incoming.filter(isValidFile);

        const uniqueFiles = validFiles.filter(file => {
            return !selectedFiles.some(selected =>
                selected.name === file.name &&
                selected.size === file.size &&
                selected.lastModified === file.lastModified
            );
        });

        if (uniqueFiles.length > getRemainingSlots()) {
            setStatus(
                `You can have a maximum of ${maxPhotos} photos in total. ` +
                `You can currently add ${Math.max(0, getRemainingSlots())}.`,
                "error"
            );

            return;
        }

        if (!uniqueFiles.length) return;

        selectedFiles.push(...uniqueFiles);

        if (syncInputFiles()) {
            renderPendingPhotos();
            updateCount();

            setStatus(
                `${selectedFiles.length} new photo(s) selected. ` +
                "Save your changes to upload them.",
                "success"
            );
        }
    }

    function isFileDrag(event) {
        return Array.from(
            event.dataTransfer?.types || []
        ).includes("Files");
    }

    function setDragging(active) {
        dropzone.classList.toggle("is-dragging", active);

        if (dropzoneTitle && dropzoneHint) {
            dropzoneTitle.textContent = active
                ? "Drop to add photos"
                : "Add photos to this café";

            dropzoneHint.textContent = active
                ? "Release to add these images."
                : "Drag and drop images here, or browse your files.";
        }
    }

    // Browse files.

    input.addEventListener("change", () => {
        addFiles(input.files);
    });

    // Existing photo removal checkboxes.
    getRemovalCheckboxes().forEach(checkbox => {
        checkbox.addEventListener("change", () => {
            updateRemovalAppearance();
            updateCount();
        });
    });

    // Drag and drop.
    dropzone.addEventListener("dragenter", event => {
        if (!isFileDrag(event)) return;

        event.preventDefault();

        dragDepth++;

        setDragging(true);
    });

    dropzone.addEventListener("dragover", event => {
        if (!isFileDrag(event)) return;

        event.preventDefault();

        event.dataTransfer.dropEffect = "copy";

        setDragging(true);
    });

    dropzone.addEventListener("dragleave", event => {
        if (!isFileDrag(event)) return;

        event.preventDefault();

        dragDepth = Math.max(0, dragDepth - 1);

        if (dragDepth === 0) {
            setDragging(false);
        }
    });

    dropzone.addEventListener("drop", event => {
        if (!isFileDrag(event)) return;

        event.preventDefault();

        dragDepth = 0;

        setDragging(false);

        addFiles(event.dataTransfer.files);
    });

    updateRemovalAppearance();
    updateCount();

    window.addEventListener("pagehide", revokePreviews);
}


onReady(() => {
    initBase()
    initFormValidation()
    initFeaturePicker()
    initLocationPicker()
    initManualClosure()
    initOpeningHours()

    initCoverImageUpload()
    initCafePhotoUpload()
    initListingPhotoLightbox()
    initOverviewEditor()

    const ratingRangeWrapper = document
        .getElementById('ratingRange')
        ?.closest('.form-range')

    if (ratingRangeWrapper) {
        // Replace the automatically-created instance with our configuration.
        Range.getInstance(ratingRangeWrapper)?.dispose()

        new Range(ratingRangeWrapper, {
            bubble: true,
            formatter: value => Number(value) === 0
                ? 'Any'
                : Number(value).toFixed(1)
        })
    }

    bindRange(
        'ratingRange',
        'ratingOut',
        (v) => Number(v).toFixed(1),
        'Any rating'
    )
    initListingMap()
    initResultsMap()
    initMapSync()
    initNearestSort()
    initOpenDatepicker()
    initShareButton()
    initYear()
})

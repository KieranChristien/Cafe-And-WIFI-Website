/*!
 * Locale — Bootstrap 6 directory template
 */

import {Chips, Datepicker} from 'bootstrap'
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
        iconAnchor: [14, 28],
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

        mapCenterLatitudeInput.value = ''
        mapCenterLongitudeInput.value = ''
        mapZoomInput.value = '18'

        mapContainer.hidden = true

        status.textContent =
            'Search for the updated address to select its location.'
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

        status.textContent = 'Finding location...'

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

            status.textContent =
                'Location found. Please select the café building.'

        } catch (error) {

            status.textContent = error.message

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


onReady(() => {
    initBase()
    initFormValidation()
    initFeaturePicker()
    initLocationPicker()

    bindRange('ratingRange', 'ratingOut', (v) => Number(v).toFixed(1))
    initListingMap()
    initResultsMap()
    initMapSync()
    initOpenDatepicker()
    initShareButton()
    initYear()
})

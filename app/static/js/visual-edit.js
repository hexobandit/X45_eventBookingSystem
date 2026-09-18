/**
 * Visual Event Editor - vanilla JS
 * Modules: Field Sync, Image Upload, Image Position Drag, Save
 */
(function () {
    'use strict';

    // --- Config & state ---
    var eventId = document.getElementById('eventId').value || '';
    var csrfToken = document.getElementById('csrfToken').value;
    var saveEndpoint = document.getElementById('saveEndpoint').value;
    var uploadEndpoint = document.getElementById('uploadEndpoint').value;
    var heroImageUrl = document.getElementById('heroImageUrl').value;
    var bodyImageUrl = document.getElementById('bodyImageUrl').value;

    // Month names for preview
    var MONTHS_CS = [
        '', 'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
        'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'
    ];
    var MONTHS_CS_LONG = [
        '', 'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];

    // =========================================================================
    // 1. FIELD SYNC — live preview updates
    // =========================================================================

    function $(id) { return document.getElementById(id); }

    function syncField(inputId, callback) {
        var el = $(inputId);
        if (!el) return;
        el.addEventListener('input', callback);
        el.addEventListener('change', callback);
    }

    // Title
    syncField('ve-title', function () {
        var val = this.value || 'Course title';
        $('previewTitle').textContent = val;
        $('previewHeroTitle').textContent = val;
    });

    // Location + venue
    function updateLocationPreview() {
        var loc = $('ve-location').value || 'Location';
        var venue = $('ve-venue_name').value;
        $('previewLocation').textContent = loc;
        $('previewHeroLocation').textContent = venue ? loc + ' | ' + venue : loc;
    }
    syncField('ve-location', updateLocationPreview);
    syncField('ve-venue_name', updateLocationPreview);

    // Short description
    syncField('ve-short_description', function () {
        var val = this.value || 'Short course description...';
        $('previewDesc').textContent = val;
        $('shortDescCount').textContent = this.value.length + '/300';
    });

    // Init char count
    (function () {
        var sd = $('ve-short_description');
        if (sd) $('shortDescCount').textContent = sd.value.length + '/300';
    })();

    // Date
    syncField('ve-event_date', function () {
        var val = this.value;
        if (!val) {
            $('previewDay').textContent = '--';
            $('previewMonth').textContent = '---';
            $('previewDateFull').textContent = '';
            return;
        }
        var d = new Date(val);
        var day = String(d.getDate()).padStart(2, '0');
        var month = d.getMonth() + 1;
        $('previewDay').textContent = day;
        $('previewMonth').textContent = MONTHS_CS[month] || '';
        $('previewDateFull').textContent = d.getDate() + '. ' + MONTHS_CS_LONG[month] + ' ' + d.getFullYear();
    });

    // Event type
    syncField('ve-event_type', function () {
        var val = this.value;
        var labels = { workshop: 'Workshop', seminar: 'Seminar', course: 'Course', conference: 'Conference' };
        $('previewType').textContent = labels[val] || val;
    });

    // =========================================================================
    // 2. VALIDATION — dates + numeric fields
    // =========================================================================

    // End date cannot be before start date
    function validateEndDate() {
        var startEl = $('ve-event_date');
        var endEl = $('ve-end_date');
        if (!startEl || !endEl || !endEl.value) return;

        if (startEl.value && endEl.value < startEl.value) {
            endEl.value = startEl.value;
            endEl.classList.add('ve-input-error');
            setTimeout(function () { endEl.classList.remove('ve-input-error'); }, 1500);
        }
    }

    (function () {
        var startEl = $('ve-event_date');
        var endEl = $('ve-end_date');
        if (startEl) {
            startEl.addEventListener('change', function () {
                // Update min on end date
                if (endEl) endEl.min = this.value;
                validateEndDate();
            });
            // Set initial min
            if (endEl && startEl.value) endEl.min = startEl.value;
        }
        if (endEl) endEl.addEventListener('change', validateEndDate);
    })();

    // Numeric-only enforcement on number inputs
    // (type="number" still allows 'e', '+', '-' in some browsers)
    (function () {
        var numericIds = ['ve-capacity', 've-price'];
        numericIds.forEach(function (id) {
            var el = $(id);
            if (!el) return;

            el.addEventListener('keydown', function (e) {
                // Allow: backspace, delete, tab, escape, enter, arrows, home, end
                var allowed = [8, 9, 13, 27, 46, 35, 36, 37, 38, 39, 40];
                if (allowed.indexOf(e.keyCode) !== -1) return;
                // Allow Ctrl/Cmd + A, C, V, X
                if ((e.ctrlKey || e.metaKey) && [65, 67, 86, 88].indexOf(e.keyCode) !== -1) return;
                // Allow decimal point for price
                if (id === 've-price' && (e.key === '.' || e.key === ',')) return;
                // Block non-numeric
                if (e.key < '0' || e.key > '9') {
                    e.preventDefault();
                }
            });

            // Strip non-numeric on paste
            el.addEventListener('paste', function (e) {
                var pasted = (e.clipboardData || window.clipboardData).getData('text');
                var pattern = id === 've-price' ? /[^0-9.]/g : /[^0-9]/g;
                var cleaned = pasted.replace(pattern, '');
                if (cleaned !== pasted) {
                    e.preventDefault();
                    // Insert cleaned value
                    document.execCommand('insertText', false, cleaned);
                }
            });
        });
    })();

    // =========================================================================
    // 3. IMAGE UPLOAD — dropzone + FileReader preview
    // =========================================================================

    function setupDropzone(dropzoneId, fileInputId, previewImgId, placeholderId, imageType) {
        var dropzone = $(dropzoneId);
        var fileInput = $(fileInputId);
        var previewImg = $(previewImgId);
        var placeholder = $(placeholderId);
        if (!dropzone || !fileInput) return;

        // Click to browse
        dropzone.addEventListener('click', function (e) {
            if (e.target === fileInput) return;
            fileInput.click();
        });

        // Drag events
        dropzone.addEventListener('dragover', function (e) {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
        dropzone.addEventListener('dragleave', function () {
            dropzone.classList.remove('dragover');
        });
        dropzone.addEventListener('drop', function (e) {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                handleFile(e.dataTransfer.files[0]);
            }
        });

        // File input change
        fileInput.addEventListener('change', function () {
            if (this.files.length) handleFile(this.files[0]);
        });

        function handleFile(file) {
            if (!file.type.startsWith('image/')) return;

            // Instant preview via FileReader
            var reader = new FileReader();
            reader.onload = function (e) {
                if (previewImg) {
                    previewImg.src = e.target.result;
                    previewImg.style.display = '';
                }
                if (placeholder) placeholder.style.display = 'none';

                // Update card + hero preview for hero images
                if (imageType === 'hero') {
                    $('previewCardImage').src = e.target.result;
                    $('previewCardImage').style.display = '';
                    $('previewHeroImage').src = e.target.result;
                    $('previewHeroImage').style.display = '';
                }
            };
            reader.readAsDataURL(file);

            // Upload to server
            uploadImage(file, imageType);
        }
    }

    function uploadImage(file, imageType) {
        var formData = new FormData();
        formData.append('image', file);
        formData.append('event_id', eventId);
        formData.append('image_type', imageType);

        fetch(uploadEndpoint, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body: formData
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    if (imageType === 'hero') {
                        heroImageUrl = data.url;
                        $('heroImageUrl').value = data.url;
                    } else {
                        bodyImageUrl = data.url;
                        $('bodyImageUrl').value = data.url;
                    }
                }
            })
            .catch(function (err) {
                console.error('Upload error:', err);
            });
    }

    setupDropzone('heroDropzone', 'heroFileInput', 'heroDropzonePreview', 'heroDropzonePlaceholder', 'hero');
    setupDropzone('bodyDropzone', 'bodyFileInput', 'bodyDropzonePreview', 'bodyDropzonePlaceholder', 'body');

    // =========================================================================
    // 4. IMAGE POSITION DRAG — mouse + touch on card image
    // =========================================================================

    (function () {
        var dragArea = $('cardImageDrag');
        var slider = $('ve-image_position_y');
        var cardImg = $('previewCardImage');
        var heroImg = $('previewHeroImage');
        if (!dragArea || !slider) return;

        var dragging = false;
        var startY = 0;
        var startPos = 50;

        function setPosition(val) {
            val = Math.max(0, Math.min(100, Math.round(val)));
            slider.value = val;
            var style = 'center ' + val + '%';
            if (cardImg) cardImg.style.objectPosition = style;
            if (heroImg) heroImg.style.objectPosition = style;
        }

        // Slider sync
        slider.addEventListener('input', function () {
            setPosition(parseInt(this.value, 10));
        });

        // Mouse drag
        dragArea.addEventListener('mousedown', function (e) {
            if (e.target === dragArea.querySelector('input')) return;
            dragging = true;
            startY = e.clientY;
            startPos = parseInt(slider.value, 10);
            dragArea.classList.add('dragging');
            e.preventDefault();
        });

        document.addEventListener('mousemove', function (e) {
            if (!dragging) return;
            var delta = e.clientY - startY;
            // Invert: drag down = show higher part = lower value
            var newPos = startPos - (delta / 2);
            setPosition(newPos);
        });

        document.addEventListener('mouseup', function () {
            if (dragging) {
                dragging = false;
                dragArea.classList.remove('dragging');
            }
        });

        // Touch drag
        dragArea.addEventListener('touchstart', function (e) {
            if (e.touches.length !== 1) return;
            dragging = true;
            startY = e.touches[0].clientY;
            startPos = parseInt(slider.value, 10);
            dragArea.classList.add('dragging');
        }, { passive: true });

        dragArea.addEventListener('touchmove', function (e) {
            if (!dragging || e.touches.length !== 1) return;
            e.preventDefault();
            var delta = e.touches[0].clientY - startY;
            var newPos = startPos - (delta / 2);
            setPosition(newPos);
        }, { passive: false });

        dragArea.addEventListener('touchend', function () {
            if (dragging) {
                dragging = false;
                dragArea.classList.remove('dragging');
            }
        });
    })();

    // =========================================================================
    // 5. LECTURERS REPEATER
    // =========================================================================

    (function () {
        var list = $('lecturersList');
        var addBtn = $('addLecturerBtn');
        if (!list || !addBtn) return;

        function createRow(name, role) {
            var row = document.createElement('div');
            row.className = 've-lecturer-row';
            row.innerHTML =
                '<div class="ve-row">' +
                '  <div class="ve-field">' +
                '    <label>Name</label>' +
                '    <input type="text" class="ve-input ve-lecturer-name" value="' + escAttr(name) + '" placeholder="Lecturer name">' +
                '  </div>' +
                '  <div class="ve-field">' +
                '    <label>Role</label>' +
                '    <input type="text" class="ve-input ve-lecturer-role" value="' + escAttr(role) + '" placeholder="Lead lecturer">' +
                '  </div>' +
                '</div>' +
                '<button type="button" class="ve-lecturer-remove" title="Remove">&times;</button>';

            row.querySelector('.ve-lecturer-remove').addEventListener('click', function () {
                row.remove();
            });

            return row;
        }

        function escAttr(s) {
            return (s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
        }

        // Load existing lecturers
        var initial = [];
        try {
            var raw = $('lecturersData').value;
            if (raw) initial = JSON.parse(raw);
        } catch (e) { /* ignore */ }

        // Ensure at least 3 rows
        var count = Math.max(3, initial.length);
        for (var i = 0; i < count; i++) {
            var l = initial[i] || {};
            list.appendChild(createRow(l.name || '', l.role || ''));
        }

        addBtn.addEventListener('click', function () {
            list.appendChild(createRow('', ''));
        });

        // Export for collectData
        window._collectLecturers = function () {
            var rows = list.querySelectorAll('.ve-lecturer-row');
            var result = [];
            rows.forEach(function (row) {
                var name = row.querySelector('.ve-lecturer-name').value.trim();
                var role = row.querySelector('.ve-lecturer-role').value.trim();
                if (name) result.push({ name: name, role: role });
            });
            return result;
        };
    })();

    // =========================================================================
    // 5b. "INCLUDED IN THE PRICE" REPEATER
    // =========================================================================

    (function () {
        var list = $('includesList');
        var addBtn = $('addIncludeBtn');
        if (!list || !addBtn) return;

        // Same defaults the public course page falls back to when empty
        var DEFAULT_INCLUDES = [
            'Course materials',
            'Certificate of completion',
            'Refreshments',
            'Hands-on practice'
        ];

        function escAttr(s) {
            return (s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
        }

        function createRow(text) {
            var row = document.createElement('div');
            row.className = 've-lecturer-row';
            row.innerHTML =
                '<div class="ve-row">' +
                '  <div class="ve-field">' +
                '    <input type="text" class="ve-input ve-include-item" value="' + escAttr(text) + '" placeholder="Course materials">' +
                '  </div>' +
                '</div>' +
                '<button type="button" class="ve-lecturer-remove" title="Remove">&times;</button>';
            row.querySelector('.ve-lecturer-remove').addEventListener('click', function () {
                row.remove();
            });
            return row;
        }

        // Parse stored HTML (<ul><li>…</li></ul> or legacy rich text) into items
        var initial = [];
        var raw = $('includesData') ? $('includesData').value : '';
        if (raw) {
            var doc = new DOMParser().parseFromString(raw, 'text/html');
            var nodes = doc.querySelectorAll('li');
            if (!nodes.length) nodes = doc.querySelectorAll('p');
            nodes.forEach(function (n) {
                var t = n.textContent.trim();
                if (t) initial.push(t);
            });
            // legacy plain text without any markup
            if (!initial.length && doc.body.textContent.trim()) {
                initial = doc.body.textContent.split('\n')
                    .map(function (s) { return s.trim(); })
                    .filter(Boolean);
            }
        }
        if (!initial.length) initial = DEFAULT_INCLUDES.slice();

        initial.forEach(function (t) { list.appendChild(createRow(t)); });

        addBtn.addEventListener('click', function () {
            list.appendChild(createRow(''));
        });

        function escHtml(s) {
            return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

        // Export for collectData — builds the <ul> the public page renders
        window._collectIncludes = function () {
            var items = [];
            list.querySelectorAll('.ve-include-item').forEach(function (input) {
                var t = input.value.trim();
                if (t) items.push('<li>' + escHtml(t) + '</li>');
            });
            return items.length ? '<ul>' + items.join('') + '</ul>' : '';
        };
    })();

    // =========================================================================
    // 6. SUMMERNOTE WYSIWYG INIT
    // =========================================================================

    var summernoteFields = ['ve-description', 've-program', 've-what_you_learn', 've-target_audience'];

    /**
     * Sanitize pasted HTML: keep only semantic structure (paragraphs, lists,
     * bold/italic/underline, links), drop every attribute except href so the
     * site's own stylesheet takes over. Headings become bold paragraphs.
     */
    var PASTE_KEEP_TAGS = { P: 'p', UL: 'ul', OL: 'ol', LI: 'li', B: 'b', STRONG: 'strong', I: 'i', EM: 'em', U: 'u', A: 'a', BR: 'br' };
    var PASTE_HEADING_TAGS = { H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1 };
    var PASTE_DROP_TAGS = { SCRIPT: 1, STYLE: 1, META: 1, LINK: 1, TITLE: 1, HEAD: 1 };

    function sanitizeChildren(srcNode, destNode, doc) {
        for (var i = 0; i < srcNode.childNodes.length; i++) {
            var child = srcNode.childNodes[i];
            if (child.nodeType === 3) { // text
                destNode.appendChild(doc.createTextNode(child.nodeValue.replace(/ /g, ' ')));
            } else if (child.nodeType === 1) {
                var tag = child.tagName;
                if (PASTE_DROP_TAGS[tag]) continue;
                // Google Docs wraps everything in <b style="font-weight:normal"> — unwrap it
                if ((tag === 'B' || tag === 'STRONG') && /font-weight\s*:\s*(normal|400)/i.test(child.getAttribute('style') || '')) {
                    sanitizeChildren(child, destNode, doc);
                } else if (PASTE_HEADING_TAGS[tag]) {
                    var p = doc.createElement('p');
                    var strong = doc.createElement('strong');
                    sanitizeChildren(child, strong, doc);
                    p.appendChild(strong);
                    destNode.appendChild(p);
                } else if (PASTE_KEEP_TAGS[tag]) {
                    var el = doc.createElement(PASTE_KEEP_TAGS[tag]);
                    if (tag === 'A') {
                        var href = child.getAttribute('href') || '';
                        if (/^https?:\/\//i.test(href) || /^mailto:/i.test(href)) el.setAttribute('href', href);
                    }
                    sanitizeChildren(child, el, doc);
                    destNode.appendChild(el);
                } else {
                    // unknown wrapper (span, div, font, table...) — unwrap, keep content
                    sanitizeChildren(child, destNode, doc);
                }
            }
        }
    }

    function cleanPastedHtml(html) {
        // DOMParser yields an inert document: no scripts run, no resources load
        var parsed = new DOMParser().parseFromString(html, 'text/html');
        var out = document.createElement('div');
        sanitizeChildren(parsed.body, out, document);
        // drop empty paragraphs/elements left after stripping
        return out.innerHTML.replace(/<p>\s*<\/p>/g, '').trim();
    }

    var summernoteConfig = {
        lang: 'en-US',
        // no fixed height — editors start compact and grow with content
        minHeight: 90,
        toolbar: [
            // 'clear' strips inline styling from the current selection
            ['style', ['bold', 'italic', 'underline', 'clear']],
            ['para', ['ul', 'ol', 'paragraph']],
            ['insert', ['link']],
            // 'cleanhtml' (custom, below) sanitizes the whole field
            ['view', ['codeview', 'cleanhtml']]
        ],
        buttons: {
            cleanhtml: function (context) {
                var ui = jQuery.summernote.ui;
                return ui.button({
                    contents: '<i class="note-icon-eraser"></i> Clean all',
                    tooltip: 'Strip ALL formatting in this field (keeps paragraphs, lists, bold, links)',
                    click: function () {
                        var code = context.invoke('code');
                        context.invoke('code', cleanPastedHtml(code));
                    }
                }).render();
            }
        },
        callbacks: {
            onPaste: function (e) {
                var clipboard = (e.originalEvent || e).clipboardData;
                if (!clipboard) return;
                var html = clipboard.getData('text/html');
                var text = clipboard.getData('text/plain');
                if (!html && !text) return;
                e.preventDefault();
                var clean;
                if (html) {
                    clean = cleanPastedHtml(html);
                } else {
                    // plain text: escape and turn line breaks into paragraphs
                    var esc = document.createElement('div');
                    esc.textContent = text;
                    clean = '<p>' + esc.innerHTML.replace(/\r?\n\r?\n/g, '</p><p>').replace(/\r?\n/g, '<br>') + '</p>';
                }
                if (clean) {
                    jQuery(this).summernote('pasteHTML', clean);
                }
            }
        }
    };

    // Initialize Summernote on all HTML fields
    if (window.jQuery) {
        summernoteFields.forEach(function (id) {
            var el = $(id);
            if (el) {
                jQuery('#' + id).summernote(summernoteConfig);
            }
        });
    }

    /**
     * Get content from a field — uses Summernote API for WYSIWYG fields,
     * plain .value for regular inputs.
     */
    function getFieldValue(id) {
        if (window.jQuery && summernoteFields.indexOf(id) !== -1) {
            var content = jQuery('#' + id).summernote('code');
            // Summernote returns '<p><br></p>' for empty — normalize to ''
            if (content === '<p><br></p>' || content === '<br>') return '';
            return content;
        }
        var el = $(id);
        return el ? el.value : '';
    }

    // =========================================================================
    // 6c. PLAIN TEXTAREAS — start compact, auto-grow with content
    // =========================================================================

    (function () {
        var areas = document.querySelectorAll('.ve-form-panel textarea:not(.ve-summernote):not([readonly])');
        areas.forEach(function (ta) {
            function grow() {
                ta.style.height = 'auto';
                ta.style.height = (ta.scrollHeight + 2) + 'px';
            }
            ta.addEventListener('input', grow); // fires on typing and paste
            grow();
        });
    })();

    // =========================================================================
    // 6b. WRITING GUIDE — copy AI prompt
    // =========================================================================

    (function () {
        var copyBtn = $('copyPromptBtn');
        var promptEl = $('aiPromptText');
        if (!copyBtn || !promptEl) return;

        copyBtn.addEventListener('click', function () {
            var text = promptEl.value;
            function done() {
                copyBtn.textContent = 'Copied!';
                copyBtn.classList.add('copied');
                setTimeout(function () {
                    copyBtn.textContent = 'Copy prompt';
                    copyBtn.classList.remove('copied');
                }, 2000);
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(done).catch(function () {
                    promptEl.select();
                    document.execCommand('copy');
                    done();
                });
            } else {
                promptEl.select();
                document.execCommand('copy');
                done();
            }
        });
    })();

    // =========================================================================
    // 7. SAVE — button + Ctrl/Cmd+S
    // =========================================================================

    function collectData() {
        return {
            id: eventId || null,
            slug: $('ve-slug') ? $('ve-slug').value : '',
            title: $('ve-title').value,
            event_date: $('ve-event_date').value,
            end_date: $('ve-end_date').value,
            location: $('ve-location').value,
            venue_name: $('ve-venue_name').value,
            short_description: $('ve-short_description').value,
            description: getFieldValue('ve-description'),
            program: getFieldValue('ve-program'),
            what_you_learn: getFieldValue('ve-what_you_learn'),
            target_audience: getFieldValue('ve-target_audience'),
            includes: window._collectIncludes ? window._collectIncludes() : '',
            event_type: $('ve-event_type').value,
            event_category: $('ve-event_category').value,
            capacity: $('ve-capacity').value,
            price: $('ve-price').value,
            currency: $('ve-currency') ? $('ve-currency').value : 'EUR',
            price_includes_vat: $('ve-price_includes_vat') ? $('ve-price_includes_vat').checked : false,
            price_note: $('ve-price_note').value,
            is_active: $('ve-is_active').checked,
            // Featured checkbox is hidden (future feature) — omit so the server
            // keeps whatever is stored
            is_featured: $('ve-is_featured') ? $('ve-is_featured').checked : undefined,
            registration_open: $('ve-registration_open').checked,
            registration_opens_at: $('ve-registration_opens_at') ? $('ve-registration_opens_at').value : '',
            external_registration_url: $('ve-external_registration_url') ? $('ve-external_registration_url').value : '',
            image_position_y: $('ve-image_position_y').value,
            image_url: $('heroImageUrl').value,
            body_image_url: $('bodyImageUrl').value,
            lecturers: window._collectLecturers ? window._collectLecturers() : []
        };
    }

    /** Point the full-page preview iframe + header link at the saved course. */
    function updateFullPreview(slug) {
        $('eventSlug').value = slug;
        var base = $('coursesBaseUrl').value.replace(/\/$/, '');
        var pageUrl = base + '/' + encodeURIComponent(slug);

        var viewBtn = $('viewSiteBtn');
        if (viewBtn) {
            viewBtn.href = pageUrl;
            viewBtn.style.display = '';
        }

        var frame = $('fullPreviewFrame');
        if (frame) {
            var empty = $('fullPreviewEmpty');
            if (empty) empty.remove();
            var note = $('fullPreviewNote');
            if (note) note.textContent = '(reflects last saved version)';
            // cache-bust so the iframe re-renders fresh content after every save
            frame.src = pageUrl + '?_=' + Date.now();
        }
    }

    function setStatus(text, cls) {
        var el = $('saveStatus');
        el.textContent = text;
        el.className = 've-save-status ' + (cls || '');
    }

    function saveEvent() {
        setStatus('Saving...', 'saving');
        var data = collectData();

        fetch(saveEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
            .then(function (result) {
                if (result.data.success) {
                    setStatus('Saved', 'saved');
                    // On first save, update ID and URL
                    if (!eventId && result.data.id) {
                        eventId = String(result.data.id);
                        $('eventId').value = eventId;
                        var newUrl = window.location.pathname + '?id=' + eventId;
                        history.replaceState(null, '', newUrl);
                    }
                    if (result.data.slug) {
                        updateFullPreview(result.data.slug);
                    }
                    // Clear status after 3s
                    setTimeout(function () { setStatus(''); }, 3000);
                } else {
                    setStatus('Error: ' + (result.data.error || 'Unknown error'), 'error');
                }
            })
            .catch(function (err) {
                setStatus('Error: ' + err.message, 'error');
            });
    }

    // Save button
    $('saveBtn').addEventListener('click', saveEvent);

    // Ctrl/Cmd+S shortcut
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            saveEvent();
        }
    });

    // =========================================================================
    // 8. REGISTRATION OPENS AT — status indicator
    // =========================================================================

    (function () {
        var regOpensInput = $('ve-registration_opens_at');
        var regCheckbox = $('ve-registration_open');
        var statusEl = $('regOpensStatus');
        if (!regOpensInput || !statusEl) return;

        function updateRegStatus() {
            var val = regOpensInput.value;
            if (!val) {
                statusEl.textContent = '';
                statusEl.style.color = '';
                return;
            }
            var opens = new Date(val).getTime();
            var now = Date.now();
            if (now >= opens) {
                statusEl.textContent = 'The registration opening time has passed — registration is open.';
                statusEl.style.color = 'var(--status-confirmed-text, #16a34a)';
                if (!regCheckbox.checked) {
                    regCheckbox.checked = true;
                }
            } else {
                var diff = opens - now;
                var d = Math.floor(diff / 86400000);
                var h = Math.floor((diff % 86400000) / 3600000);
                var m = Math.floor((diff % 3600000) / 60000);
                var parts = [];
                if (d > 0) parts.push(d + 'd');
                if (h > 0) parts.push(h + 'h');
                parts.push(m + 'min');
                statusEl.textContent = 'Registration opens in ' + parts.join(' ');
                statusEl.style.color = 'var(--admin-accent, #1e85bd)';
            }
        }

        regOpensInput.addEventListener('change', updateRegStatus);
        updateRegStatus();
        setInterval(updateRegStatus, 60000);
    })();

    // =========================================================================
    // 9. MOBILE TAB SWITCHER
    // =========================================================================

    (function () {
        var switcher = $('tabSwitcher');
        var formPanel = $('formPanel');
        var previewPanel = $('previewPanel');
        if (!switcher) return;

        var tabs = switcher.querySelectorAll('.ve-tab');
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                tabs.forEach(function (t) { t.classList.remove('active'); });
                this.classList.add('active');
                var target = this.getAttribute('data-tab');
                if (target === 'form') {
                    formPanel.classList.remove('hidden');
                    previewPanel.classList.add('hidden');
                } else {
                    formPanel.classList.add('hidden');
                    previewPanel.classList.remove('hidden');
                }
            });
        });

        // Initialize: show form by default on mobile
        function checkMobile() {
            if (window.innerWidth <= 1200) {
                previewPanel.classList.add('hidden');
                formPanel.classList.remove('hidden');
                tabs[0].classList.add('active');
                tabs[1].classList.remove('active');
            } else {
                previewPanel.classList.remove('hidden');
                formPanel.classList.remove('hidden');
            }
        }

        // Only set initial state, don't override user's tab choice on resize
        checkMobile();
    })();

})();

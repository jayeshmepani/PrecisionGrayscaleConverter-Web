document.addEventListener('DOMContentLoaded', () => {
    let currentMode = 'single';
    let singleFile = null;
    let batchFiles = [];
    let originalAspectRatio = 1;
    let isAspectLocked = true;
    let clientGrayscaleCanvas = document.createElement('canvas');

    const DOMElements = {
        modeSwitcher: document.getElementById('mode-switcher'),
        singleModePanel: document.getElementById('single-mode-panel'),
        batchModePanel: document.getElementById('batch-mode-panel'),
        form: document.getElementById('conversion-form'),
        settingsContainer: document.getElementById('settings-container'),
        convertBtn: document.getElementById('convert-btn'),
        convertBtnText: document.getElementById('convert-btn-text'),
        spinner: document.getElementById('spinner'),
        singleDropZone: document.getElementById('single-drop-zone'),
        batchDropZone: document.getElementById('batch-drop-zone'),
        previewArea: document.getElementById('preview-area'),
        originalInfo: document.getElementById('original-info'),
        originalPreview: document.getElementById('original-preview'),
        grayscalePreview: document.getElementById('grayscale-preview'),
        batchFileList: document.getElementById('batch-file-list'),
        notificationContainer: document.getElementById('notification-container'),
    };

    const FORMAT_CAPABILITIES = {
        // Correctly define PNG alpha capability as a function of bit depth
        '.png': { bitDepths: [8, 16], alpha: (bitDepth) => bitDepth === 8, quality: false, subsampling: false },
        '.jpeg': { bitDepths: [8], alpha: false, quality: true, subsampling: true },
        '.heic': { bitDepths: [8, 10], alpha: (bitDepth) => bitDepth === 8, quality: true, subsampling: true },
        '.tiff': { bitDepths: [8, 16], alpha: true, quality: false, subsampling: false },
        '.webp': { bitDepths: [8], alpha: true, quality: true, subsampling: false },
        '.bmp': { bitDepths: [8], alpha: false, quality: false, subsampling: false },
    };

    const TEMPLATES = {
        dropZoneContent: `
            <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto h-16 w-16 text-dark-text-secondary" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5V6a3 3 0 013-3h12a3 3 0 013 3v10.5M3 16.5l4.5-4.5 3 3 4.5-4.5L21 16.5M3 16.5h18" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 11.25V3.75M9 6l3-3 3 3" />
            </svg>
            <p class="mt-4 block text-lg font-medium text-dark-text-secondary">
                Drag & Drop file(s) here, or <span class="text-primary font-semibold">click to upload</span>
            </p>
            <p class="text-sm text-dark-text-secondary/80">You can also paste an image from clipboard</p>
            <input type="file" class="file-input absolute inset-0 w-full h-full opacity-0 cursor-pointer" accept="image/*,.heic,.heif" multiple>
        `,
        settingsControls: `<h3 class="text-xl font-semibold text-white">Conversion Settings</h3><div><label for="conversion-mode" class="label-text">Conversion Mode</label><select id="conversion-mode" name="conversion_mode" class="input-field mt-1"><option>L*a*b* (L*)</option><option>Gamma</option><option selected>Rec. 709</option><option>HSL (Lightness)</option><option>HSV (Value)</option><option>Rec. 601</option><option>Rec. 2100</option></select></div><div class="grid grid-cols-2 gap-4"><div><label for="output-format" class="label-text">Format</label><select id="output-format" name="output_format" class="input-field mt-1"><option value=".png">PNG</option><option value=".jpeg">JPEG</option><option value=".heic">HEIC</option><option value=".tiff">TIFF</option><option value=".webp">WEBP</option><option value=".bmp">BMP</option></select></div><div><label for="bit-depth" class="label-text">Bit Depth</label><select id="bit-depth" name="bit_depth" class="input-field mt-1"><option value="8">8-bit</option><option value="10">10-bit</option><option value="16">16-bit</option></select></div></div><div id="quality-options" class="hidden"><label for="quality" class="label-text flex justify-between"><span>Quality</span><span id="quality-value" class="font-semibold">100%</span></label><input type="range" id="quality" name="quality" min="1" max="100" value="100" class="range-slider"></div><div id="subsampling-options" class="hidden"><label for="subsampling" class="label-text">Chroma Subsampling</label><select id="subsampling" name="subsampling" class="input-field mt-1"><option value="0" selected>4:4:4 (Best)</option><option value="1">4:2:2 (High)</option><option value="2">4:2:0 (Standard)</option></select></div><div id="dimension-controls"><label class="label-text">Dimensions (WxH)</label><div class="flex items-center space-x-2 mt-1"><input type="number" id="width" name="width" placeholder="Auto" class="input-field"><input type="number" id="height" name="height" placeholder="Auto" class="input-field"><button type="button" id="aspect-lock-btn" class="p-3 bg-primary/20 rounded-lg hover:bg-dark-border transition" title="Toggle Aspect Ratio Lock"><svg id="lock-icon" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-primary" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd" /></svg><svg id="unlock-icon" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-dark-text-secondary hidden" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a5 5 0 00-5 5v2a2 2 0 00-2 2v5a2 2 0 002 2h10a2 2 0 002-2v-5a2 2 0 00-2-2V7a5 5 0 00-5-5zm1 11a1 1 0 11-2 0v-3a1 1 0 112 0v3zM12 7v2H8V7a2 2 0 114 0z" /></svg></button></div></div><div class="space-y-3 pt-2"><div id="alpha-control"><label class="flex items-center space-x-3 cursor-pointer"><input id="preserve-alpha" name="preserve_alpha" type="checkbox" class="checkbox-input"><span class="text-dark-text-main">Preserve Transparency</span></label><small id="alpha-warning" class="text-yellow-400 text-xs mt-1 ml-9" style="display: none;">16-bit transparency is only supported for TIFF format.</small></div><div><label class="flex items-center space-x-3 cursor-pointer"><input id="strip-metadata" name="strip_metadata" type="checkbox" class="checkbox-input"><span class="text-dark-text-main">Strip Metadata (EXIF, etc.)</span></label></div></div>`,
        batchFileItem: (file) => `<div class="flex items-center bg-dark-card p-3 rounded-lg" data-filename="${file.name}"><div class="flex-shrink-0"><img src="${URL.createObjectURL(file)}" class="h-12 w-12 object-cover rounded-md"></div><div class="flex-grow ml-4"><p class="font-medium text-dark-text-main truncate">${file.name}</p><p class="text-sm text-dark-text-secondary">${(file.size / 1024 / 1024).toFixed(2)} MB</p></div><div class="flex-shrink-0 ml-4"><button class="remove-batch-item-btn text-dark-text-secondary hover:text-red-500 transition" title="Remove">✖</button></div></div>`
    };

    function initialize() {
        DOMElements.settingsContainer.innerHTML = TEMPLATES.settingsControls;
        DOMElements.singleDropZone.innerHTML = TEMPLATES.dropZoneContent;
        DOMElements.batchDropZone.innerHTML = TEMPLATES.dropZoneContent;
        setupEventListeners();
        switchMode('single');
        updateUiForFormat();
    }

    function updateUiForFormat() {
        const formatSelect = document.getElementById('output-format');
        const bitDepthSelect = document.getElementById('bit-depth');
        const format = formatSelect.value;
        const caps = FORMAT_CAPABILITIES[format];
        if (!caps) return;

        Array.from(bitDepthSelect.options).forEach(opt => {
            opt.disabled = !caps.bitDepths.includes(parseInt(opt.value));
        });
        if (bitDepthSelect.options[bitDepthSelect.selectedIndex].disabled) {
            bitDepthSelect.value = caps.bitDepths[0];
        }
        const bitDepth = parseInt(bitDepthSelect.value);

        const alphaControl = document.getElementById('alpha-control');
        const alphaIsSupported = typeof caps.alpha === 'function' ? caps.alpha(bitDepth) : caps.alpha;
        alphaControl.classList.toggle('control-disabled', !alphaIsSupported);
        alphaControl.querySelector('input').disabled = !alphaIsSupported;
        if (!alphaIsSupported) {
            alphaControl.querySelector('input').checked = false;
        }

        document.getElementById('quality-options').classList.toggle('hidden', !caps.quality);
        document.getElementById('subsampling-options').classList.toggle('hidden', !caps.subsampling);

        handleLivePreview();

        // Add this new block to control the warning message
        const alphaWarning = document.getElementById('alpha-warning');
        const isUnsupportedAlpha = bitDepth > 8 && (format === '.png' || format === '.webp');
        alphaWarning.style.display = isUnsupportedAlpha ? 'block' : 'none';
    }

    function setupEventListeners() {
        DOMElements.modeSwitcher.addEventListener('click', (e) => {
            if (e.target.matches('[data-mode]')) switchMode(e.target.dataset.mode);
        });

        DOMElements.form.addEventListener('submit', handleFormSubmit);
        const debouncedPreview = debounce(handleLivePreview, 150);
        DOMElements.form.addEventListener('change', (e) => {
            if (e.target.id === 'output-format' || e.target.id === 'bit-depth') {
                updateUiForFormat();
            }
            debouncedPreview();
        });
        DOMElements.form.addEventListener('input', debouncedPreview);

        ['dragover', 'dragleave', 'drop'].forEach(eventName => {
            [DOMElements.singleDropZone, DOMElements.batchDropZone].forEach(el => el.addEventListener(eventName, handleDragDrop));
        });

        document.addEventListener('paste', handlePaste);
        document.body.addEventListener('change', (e) => { if (e.target.matches('.file-input')) handleFileSelection(e.target.files); });
        document.body.addEventListener('input', (e) => {
            if (e.target.matches('#quality')) document.getElementById('quality-value').textContent = `${e.target.value}%`;
            if (e.target.matches('#width')) handleDimensionChange('width');
            if (e.target.matches('#height')) handleDimensionChange('height');
        });
        document.body.addEventListener('click', (e) => { if (e.target.closest('#aspect-lock-btn')) toggleAspectRatioLock(); });

        DOMElements.batchFileList.addEventListener('click', (e) => {
            if (e.target.closest('.remove-batch-item-btn')) {
                const item = e.target.closest('[data-filename]');
                removeBatchFile(item.dataset.filename);
                item.remove();
            }
        });
    }

    function switchMode(newMode) {
        currentMode = newMode;
        DOMElements.singleModePanel.classList.toggle('hidden', newMode !== 'single');
        DOMElements.batchModePanel.classList.toggle('hidden', newMode !== 'batch');
        DOMElements.modeSwitcher.querySelector('[data-mode="single"]').classList.toggle('active', newMode === 'single');
        DOMElements.modeSwitcher.querySelector('[data-mode="batch"]').classList.toggle('active', newMode !== 'single');
        document.getElementById('dimension-controls').style.display = newMode === 'single' ? 'block' : 'none';
        updateButtonState();
    }

    function handleFileSelection(files) {
        if (!files || files.length === 0) return;
        if (currentMode === 'single' || files.length === 1) {
            switchMode('single');
            handleSingleFile(files[0]);
        } else {
            switchMode('batch');
            handleBatchFiles(Array.from(files));
        }
    }

    async function handleSingleFile(file) {
        if (!file) return;
        singleFile = file;
        DOMElements.previewArea.classList.remove('hidden');
        DOMElements.originalInfo.textContent = 'Processing preview...';
        try {
            const compressedFile = await imageCompression(file, { maxSizeMB: 2, useWebWorker: true });
            const objectURL = URL.createObjectURL(compressedFile);
            DOMElements.originalPreview.src = objectURL;
            DOMElements.grayscalePreview.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
            const img = new Image();
            img.onload = () => {
                originalAspectRatio = img.width / img.height;
                document.getElementById('width').value = img.width;
                document.getElementById('height').value = img.height;
                DOMElements.originalInfo.textContent = `${file.name} | ${img.width}x${img.height}`;
                handleLivePreview();
            };
            img.src = objectURL;
        } catch (error) {
            DOMElements.originalInfo.textContent = "Could not create preview.";
            showNotification('Error creating image preview.', true);
        }
        updateButtonState();
    }

    function handleBatchFiles(files) {
        files.forEach(file => { if (!batchFiles.some(f => f.name === file.name)) { batchFiles.push(file); DOMElements.batchFileList.insertAdjacentHTML('beforeend', TEMPLATES.batchFileItem(file)); } });
        updateButtonState();
    }

    function removeBatchFile(filename) { batchFiles = batchFiles.filter(f => f.name !== filename); updateButtonState(); }
    function handleDragDrop(e) { e.preventDefault(); e.stopPropagation(); if (e.type === 'dragover') e.currentTarget.classList.add('drag-over'); else e.currentTarget.classList.remove('drag-over'); if (e.type === 'drop') handleFileSelection(e.dataTransfer.files); }
    function handlePaste(e) { const file = (e.clipboardData || e.originalEvent.clipboardData).items[0]?.getAsFile(); if (file) { handleFileSelection([new File([file], `pasted-image-${new Date().getTime()}.png`, { type: file.type })]); } }

    async function handleFormSubmit(e) {
        e.preventDefault();
        const url = currentMode === 'single' ? '/api/convert' : '/api/batch-convert';
        const formData = new FormData(DOMElements.form);
        if (currentMode === 'single' && singleFile) formData.append('file', singleFile, singleFile.name);
        else if (currentMode === 'batch' && batchFiles.length > 0) batchFiles.forEach(file => formData.append('files', file, file.name));
        else { showNotification('Please select at least one file.', true); return; }
        setLoading(true);
        try {
            const response = await axios.post(url, formData, { responseType: currentMode === 'batch' ? 'blob' : 'json' });
            if (currentMode === 'single') {
                const link = document.createElement('a');
                link.href = response.data.download_url;
                link.setAttribute('download', `${Path.basename(singleFile.name, Path.extname(singleFile.name))}_grayscale${getFormSettings().output_format}`);
                document.body.appendChild(link);
                link.click();
                link.remove();
                showNotification('Conversion successful!', false);
            } else {
                const url = window.URL.createObjectURL(new Blob([response.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', 'grayscale_batch.zip');
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(url);
                showNotification('Batch conversion successful!', false);
            }
        } catch (error) { showNotification(`An error occurred: ${error.response?.data?.detail || error.message}`, true); } finally { setLoading(false); }
    }

    function handleLivePreview() {
        if (currentMode !== 'single' || !singleFile) return;
        const img = DOMElements.originalPreview;
        if (!img.src || !img.complete || img.naturalWidth === 0) return;
        const settings = getFormSettings();
        const canvas = clientGrayscaleCanvas;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        ctx.drawImage(img, 0, 0);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        const sRGB_to_linear = c => (c <= 0.04045) ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        const linear_to_sRGB = c => (c <= 0.0031308) ? c * 12.92 : 1.055 * Math.pow(c, 1.0 / 2.4) - 0.055;
        for (let i = 0; i < data.length; i += 4) {
            const r_srgb = data[i] / 255.0, g_srgb = data[i + 1] / 255.0, b_srgb = data[i + 2] / 255.0;
            let gray_srgb = 0;
            switch (settings.conversion_mode) {
                case "L*a*b* (L*)": case "Rec. 709": gray_srgb = r_srgb * 0.2126 + g_srgb * 0.7152 + b_srgb * 0.0722; break;
                case "Gamma": gray_srgb = linear_to_sRGB(sRGB_to_linear(r_srgb) * 0.2126 + sRGB_to_linear(g_srgb) * 0.7152 + sRGB_to_linear(b_srgb) * 0.0722); break;
                case "Rec. 601": gray_srgb = r_srgb * 0.299 + g_srgb * 0.587 + b_srgb * 0.114; break;
                case "Rec. 2100": gray_srgb = r_srgb * 0.2627 + g_srgb * 0.6780 + b_srgb * 0.0593; break;
                case "HSL (Lightness)": gray_srgb = 0.5 * (Math.max(r_srgb, g_srgb, b_srgb) + Math.min(r_srgb, g_srgb, b_srgb)); break;
                case "HSV (Value)": gray_srgb = Math.max(r_srgb, g_srgb, b_srgb); break;
                default: gray_srgb = r_srgb * 0.2126 + g_srgb * 0.7152 + b_srgb * 0.0722;
            }
            const finalGray = Math.max(0, Math.min(255, gray_srgb * 255));
            data[i] = data[i + 1] = data[i + 2] = finalGray;
        }
        ctx.putImageData(imageData, 0, 0);
        DOMElements.grayscalePreview.src = canvas.toDataURL();
    }

    function updateButtonState() {
        const hasFiles = currentMode === 'single' ? !!singleFile : batchFiles.length > 0;
        DOMElements.convertBtn.disabled = !hasFiles;
        if (currentMode === 'batch') DOMElements.convertBtnText.textContent = hasFiles ? `Process ${batchFiles.length} File(s)` : 'Add Files to Batch';
        else DOMElements.convertBtnText.textContent = hasFiles ? 'Convert & Download' : 'Select an Image';
    }

    function setLoading(isLoading) { DOMElements.spinner.classList.toggle('hidden', !isLoading); DOMElements.convertBtn.disabled = isLoading; }
    function getFormSettings() { const s = {}; for (let [k, v] of new FormData(DOMElements.form).entries()) { const e = DOMElements.form.elements[k]; s[k] = (e && e.type === 'checkbox') ? e.checked : v; } return s; }
    function handleDimensionChange(changedInput) { if (!isAspectLocked || !originalAspectRatio) return; const w = document.getElementById('width'), h = document.getElementById('height'); const wv = parseInt(w.value, 10), hv = parseInt(h.value, 10); if (changedInput === 'width' && wv > 0) h.value = Math.round(wv / originalAspectRatio); else if (changedInput === 'height' && hv > 0) w.value = Math.round(hv * originalAspectRatio); }
    function toggleAspectRatioLock() { isAspectLocked = !isAspectLocked; const b = document.getElementById('aspect-lock-btn'); b.querySelector('#lock-icon').classList.toggle('hidden', !isAspectLocked); b.querySelector('#unlock-icon').classList.toggle('hidden', isAspectLocked); b.classList.toggle('bg-primary/20', isAspectLocked); b.classList.toggle('bg-dark-input', !isAspectLocked); }
    function showNotification(message, isError = false) { const n = document.createElement('div'); n.className = `notification ${isError ? 'bg-red-500' : 'bg-primary'}`; n.textContent = message; DOMElements.notificationContainer.appendChild(n); setTimeout(() => n.classList.add('show'), 10); setTimeout(() => { n.classList.remove('show'); setTimeout(() => n.remove(), 500); }, 4000); }
    function debounce(func, delay) { let timeout; return function (...args) { clearTimeout(timeout); timeout = setTimeout(() => func.apply(this, args), delay); }; }
    const Path = { basename: (path, ext) => { const base = path.substring(path.lastIndexOf('/') + 1); return ext && base.endsWith(ext) ? base.slice(0, -ext.length) : base; }, extname: (path) => path.substring(path.lastIndexOf('.')) };

    initialize();
});
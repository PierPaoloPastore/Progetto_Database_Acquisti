
document.addEventListener('DOMContentLoaded', function() {
    // PDF Preview
    const fileInput = document.getElementById('file-upload');
    const iframe = document.getElementById('pdf-preview-frame');
    if(fileInput && iframe) {
        fileInput.addEventListener('change', function(e) {
            if(e.target.files[0]) {
                iframe.src = URL.createObjectURL(e.target.files[0]);
            }
        });
    }

    // Filter Logic
    const searchInput = document.getElementById('invoice-search');
    if(searchInput) {
        searchInput.addEventListener('keyup', function(e) {
            const term = e.target.value.toLowerCase();
            document.querySelectorAll('.invoice-row').forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(term) ? '' : 'none';
            });
        });
    }
});

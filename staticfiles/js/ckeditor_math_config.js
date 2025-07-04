ClassicEditor
    .create(document.querySelector('#id_YOUR_FIELD_NAME'), {
        toolbar: {
            items: [
                'mathType', 'chemType',
                '|', 'bold', 'italic', 'link', 'bulletedList', 'numberedList'
            ]
        },
        licenseKey: '',
    })
    .catch(error => {
        console.error(error);
    });
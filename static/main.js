tinymce.init({
	selector: '#editor',
	lenguage:"ES",
	branding: false,
	menubar: false,
	toolbar:
		'undo redo | styles forecolor | bold italic | alignleft aligncenter alignright alignjustify | outdent indent | image',
	statusbar: false,
	plugins: 'image',
});

const formulario = document.getElementById('formulario');
formulario.addEventListener('submit', (e) => {
	e.preventDefault();

	const contenido = tinymce.activeEditor.getContent();
	console.log(contenido);
});

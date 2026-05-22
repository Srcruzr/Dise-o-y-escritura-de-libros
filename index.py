from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, abort
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from functools import wraps
import io
import base64
from PIL import Image
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = 'xyzsdfg'

# Configuración de MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'user-system'

mysql = MySQL(app)

app.config['UPLOAD_FOLDER'] = 'static/profile_images'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024 

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/about', methods=['GET', 'POST'])
@login_required
def about():
    if request.method == 'POST':
        texto = request.form['texto']
        libro_id = request.form['libro_id']  # Asegúrate de obtener el ID del libro para el que se está añadiendo el texto
        cursor = mysql.connection.cursor()
        cursor.execute('UPDATE textos SET texto = %s WHERE id = %s', (texto, libro_id))
        mysql.connection.commit()
        cursor.close()
        flash('Texto del libro guardado exitosamente!', 'success')
        return redirect(url_for('index'))
    
    # Obtener libros que no tienen texto aún
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT id, titulo FROM textos WHERE texto IS NULL AND usuario_id = %s', (session['userid'],))
    libros = cursor.fetchall()
    cursor.close()
    
    return render_template('about.html', libros=libros)


@app.route('/paint')
@login_required
def paint():
    return render_template('paint.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM user WHERE email = %s AND password = %s', (email, password))
        user = cursor.fetchone()

        if user:
            session['loggedin'] = True
            session['userid'] = user['userid']
            session['name'] = user['name']
            session['profile_image'] = user['profile_image']  # Añadido para almacenar la imagen de perfil
            flash('¡Has iniciado sesión exitosamente!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Email o contraseña incorrectos', 'error')

    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if request.method == 'POST':
        session.pop('loggedin', None)
        session.pop('userid', None)
        session.pop('email', None)
        session.pop('name', None)
        session.pop('profile_image', None)
        return redirect(url_for('login'))
    return redirect(url_for('confirm_logout'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ''
    if request.method == 'POST' and 'name' in request.form and 'password' in request.form and 'email' in request.form:
        userName = request.form['name']
        password = request.form['password']
        email = request.form['email']
        
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM user WHERE email = %s', (email,))
        account = cursor.fetchone()
        
        if account:
            message = 'El email ya está registrado!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            message = 'Dirección de email inválida!'
        elif not userName or not password or not email:
            message = '¡Por favor, completa todos los campos!'
        else:
            cursor.execute('INSERT INTO user (name, email, password) VALUES (%s, %s, %s)', (userName, email, password))
            mysql.connection.commit()
            message = '¡Te has registrado exitosamente!'
    
    elif request.method == 'POST':
        message = '¡Por favor, completa todos los campos!'
    
    return render_template('register.html', message=message)

@app.route('/confirmlog')
def confirm_logout():
    return render_template('confirmlog.html')

@app.route('/guardar_texto', methods=['POST'])
@login_required
def guardar_texto():
    if 'texto' in request.form:
        texto = request.form['texto']
        usuario_id = session['userid']
        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO textos (usuario_id, texto) VALUES (%s, %s)', (usuario_id, texto))
        mysql.connection.commit()
        cursor.close()
        flash('Texto guardado exitosamente!', 'success')
    return redirect(url_for('index'))

@app.route('/write_book', methods=['GET', 'POST'])
@login_required
def write_book():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        usuario_id = session['userid']
        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO textos (usuario_id, titulo, descripcion) VALUES (%s, %s, %s)', (usuario_id, title, description))
        mysql.connection.commit()
        cursor.close()
        flash('Libro guardado exitosamente! Ahora añade el texto del libro.', 'success')
        return redirect(url_for('about'))
    return render_template('write_book.html')



@app.route('/guardar_imagen', methods=['POST'])
@login_required
def guardar_imagen():
    data = request.get_json()
    image_data = data['image']

    # Extraer datos de imagen desde el string base64
    image_data = image_data.split(',')[1]
    image_bytes = base64.b64decode(image_data)
    
    cursor = mysql.connection.cursor()

    try:
        # Insertar la imagen en la base de datos
        cursor.execute('INSERT INTO imagenes (usuario_id, imagen) VALUES (%s, %s)', (session['userid'], image_bytes))
        mysql.connection.commit()
        flash('Imagen guardada exitosamente!', 'success')
        response = {'success': True, 'message': 'Imagen guardada exitosamente!'}
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al guardar la imagen: {str(e)}', 'error')
        response = {'success': False, 'message': f'Error al guardar la imagen: {str(e)}'}
    finally:
        cursor.close()

    return jsonify(response)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        new_name = request.form['name']
        new_password = request.form['password']
        new_image = request.files.get('image')

        cursor = mysql.connection.cursor()

        if new_name:
            cursor.execute('UPDATE user SET name = %s WHERE userid = %s', (new_name, session['userid']))
            session['name'] = new_name

        if new_password:
            cursor.execute('UPDATE user SET password = %s WHERE userid = %s', (new_password, session['userid']))

        if new_image:
            # Guardar imagen en la carpeta de imágenes de perfil
            image_filename = new_image.filename
            image_path = f'static/profile_images/{image_filename}'
            new_image.save(image_path)
            cursor.execute('UPDATE user SET profile_image = %s WHERE userid = %s', (image_filename, session['userid']))
            session['profile_image'] = image_filename  # Actualiza la imagen en la sesión

        mysql.connection.commit()
        cursor.close()

        flash('Perfil actualizado exitosamente!', 'success')
        return redirect(url_for('edit_profile'))

    return render_template('edit_profile.html')

@app.route('/profile_image/<filename>')
def profile_image(filename):
    return send_from_directory('static/profile_images', filename)

@app.route('/libros')
def libros():
    cursor = mysql.connection.cursor()
    cursor.execute('''
        SELECT t.id, t.titulo, t.descripcion, i.imagen
        FROM textos t
        LEFT JOIN imagenes i ON t.usuario_id = i.usuario_id
        WHERE i.imagen IS NOT NULL
    ''')
    libros = cursor.fetchall()
    cursor.close()

    libros_data = []
    for libro in libros:
        libro_id, titulo, descripcion, imagen = libro
        if imagen:
            imagen_base64 = base64.b64encode(imagen).decode('utf-8')
            libros_data.append({'id': libro_id, 'titulo': titulo, 'descripcion': descripcion, 'imagen': imagen_base64})
        else:
            libros_data.append({'id': libro_id, 'titulo': titulo, 'descripcion': descripcion, 'imagen': None})

    return render_template('libros.html', libros=libros_data)

@app.route('/libro/<int:libro_id>')
def libro(libro_id):
    cursor = mysql.connection.cursor()
    cursor.execute('''
        SELECT t.titulo, t.descripcion, t.texto
        FROM textos t
        WHERE t.id = %s
    ''', (libro_id,))
    libro = cursor.fetchone()
    cursor.close()

    if libro:
        libro = {'titulo': libro[0], 'descripcion': libro[1], 'texto': libro[2]}
        return render_template('libro.html', libro=libro)
    else:
        abort(404)

@app.template_filter('strip_html')
def strip_html(text):
    if text:
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text()
    return ''

def redimensionar_imagen(image_path, output_path, tamaño=(800, 600)):
    with Image.open(image_path) as img:
        img = img.resize(tamaño, Image.ANTIALIAS)
        img.save(output_path)

def obtener_comentarios(imagen_id):
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT comentario, fecha FROM comentarios WHERE imagen_id = %s ORDER BY fecha DESC', (imagen_id,))
    comentarios = cursor.fetchall()
    cursor.close()
    return comentarios

import base64


def base64_encode_image(image):
    return base64.b64encode(image).decode('utf-8')

@app.route('/ilustraciones')
def ilustraciones():
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT id, imagen FROM imagenes')
    imagenes = cursor.fetchall()
    cursor.close()

    imagenes_data = []
    for imagen in imagenes:
        imagen_id, imagen_bytes = imagen
        imagen_base64 = base64.b64encode(imagen_bytes).decode('utf-8')
        comentarios = obtener_comentarios(imagen_id)  # Función para obtener comentarios de la imagen
        imagenes_data.append({
            'imagen_id': imagen_id,
            'imagen_base64': imagen_base64,
            'comentarios': comentarios
        })

    return render_template('ilustraciones.html', imagenes_data=imagenes_data)

@app.route('/guardar_comentario', methods=['POST'])
@login_required
def guardar_comentario():
    if request.method == 'POST':
        comentario = request.form['comentario']
        imagen_id = request.form['imagen_id']
        usuario_id = session['userid']
        
        cursor = mysql.connection.cursor()
        try:
            cursor.execute('INSERT INTO comentarios (usuario_id, imagen_id, comentario) VALUES (%s, %s, %s)',
                           (usuario_id, imagen_id, comentario))
            mysql.connection.commit()
            flash('Comentario añadido correctamente!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error al añadir comentario: {str(e)}', 'error')
        finally:
            cursor.close()
        
        return redirect(url_for('ilustraciones'))
        
if __name__ == "__main__":
    app.run(debug=True)

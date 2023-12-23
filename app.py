import os
from flask import Flask, abort, render_template, request, redirect, session, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import psycopg2
from passlib.hash import bcrypt
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = '123'

login_manager = LoginManager()
login_manager.init_app(app) 

# Конфигурация базы данных
db_params = {
    'host': '127.0.0.1',
    'port': '5432',
    'database': 'offer_of_services',
    'user': 'naggets_knowledge_base',
    'password': '81212'
}

# Подключение к базе данных
def connect_db():
    return psycopg2.connect(**db_params)

class ProfileForm:
    def __init__(self, username, service_type, experience, service_price, about_me):
        self.username = username
        self.service_type = service_type
        self.experience = experience
        self.service_price = service_price
        self.about_me = about_me

class User(UserMixin):
    def __init__(self, user_id, username, role='user'):
        self.id = user_id
        self.username = username
        self.role = role


# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

@login_manager.user_loader
def load_user(user_id):
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
                user_data = cursor.fetchone()

        if user_data:
            return User(user_data[0], user_data[1])
    except psycopg2.Error as e:
        # Обработка ошибок подключения к базе данных
        print(f"Database error: {e}")
    return None

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            with psycopg2.connect(**db_params) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    existing_user_id = cursor.fetchone()

            if existing_user_id:
                return render_template('register.html', error='Username already exists')

            hashed_password = bcrypt.hash(password)

            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
                conn.commit()

            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                user_id = cursor.fetchone()[0]

            if user_id:
                user = User(user_id, username)
                login_user(user)
                return redirect(url_for('profiles_form'))
        except psycopg2.Error as e:
            print(f"Database error: {e}")

    return render_template('register.html')




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            with psycopg2.connect(**db_params) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
                    user_data = cursor.fetchone()

            if user_data and bcrypt.verify(password, user_data[2]):
                user = User(user_data[0], user_data[1])
                login_user(user)
                
                # Сохраняем имя пользователя в сессии
                session['username'] = username
                
                return redirect(url_for('main'))
        except psycopg2.Error as e:
            print(f"Database error: {e}")

    return render_template('login.html')


@app.route('/main')
def main():
    return render_template('main.html')

# Добавьте маршрут для выхода из системы, если не существует
@app.route('/logout')
@login_required
def logout():
    logout_user()
    
    # Удаляем имя пользователя из сессии при выходе
    session.pop('username', None)
    
    flash('Выход выполнен успешно', 'success')
    return redirect(url_for('index'))

from flask import request


# Функция для получения данных анкет с учетом фильтров
def get_filtered_anketa_list(username, search_age=None, search_gender=None, offset=0, limit=3):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            query = """
                SELECT username, age, gender, about_me, photo
                FROM questionary
                WHERE username != %s AND is_visible = true
                    AND (age = %s OR %s IS NULL)
                    AND (gender = %s OR %s IS NULL)
                ORDER BY id
                OFFSET %s LIMIT %s
            """
            cursor.execute(query, (username, search_age, search_age, search_gender, search_gender, offset, limit))
            anketa_list = cursor.fetchall()
    return anketa_list

# Маршрут для просмотра профилей (доступен для всех)
@app.route('/profiles', methods=['GET', 'POST'])
def view_profiles():
    

    # Проверка, залогинен ли пользователь
    if 'username' not in session:
        flash('Для доступа к этой странице войдите в аккаунт', 'error')
        return redirect(url_for('login'))

    username = session['username']
    offset = int(request.args.get('offset', 0))
    limit = 5

    if request.method == 'POST':
        # Обработка поиска при отправке формы
        service_type = request.form.get('service_type')
        min_experience = request.form.get('min_experience')
        max_experience = request.form.get('max_experience')
        min_price = request.form.get('min_price')
        max_price = request.form.get('max_price')
    else:
        # Обработка поиска при использовании параметров в URL
        service_type = request.args.get('service_type', '')
        min_experience = request.args.get('min_experience', '')
        max_experience = request.args.get('max_experience', '')
        min_price = request.args.get('min_price', '')
        max_price = request.args.get('max_price', '')

    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                # Добавляем условия поиска
                query = """
                    SELECT id, username, service_type, experience, service_price, about_me, created_at
                    FROM profiles
                """

                # Составляем условия для фильтрации
                conditions = []
                if service_type:
                    conditions.append(f"service_type = '{service_type}'")
                if min_experience:
                    conditions.append(f"experience >= {min_experience}")
                if max_experience:
                    conditions.append(f"experience <= {max_experience}")
                if min_price:
                    conditions.append(f"service_price >= {min_price}")
                if max_price:
                    conditions.append(f"service_price <= {max_price}")

                # Добавляем условия к запросу, если они есть
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                

                    # Получаем список анкет из базы данных
                anketa_list = get_filtered_anketa_list(username, offset=offset, limit=limit)

               

        return render_template('profiles.html', anketa_list=anketa_list, offset=offset, limit=limit)
    
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        abort(500, f"Internal Server Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        abort(500, f"Internal Server Error: {e}")



# Маршрут для формы профиля
@app.route('/profiles_form', methods=['GET', 'POST'])
@login_required
def profiles_form():
    if request.method == 'POST':
        name = request.form.get('name')
        service_type = request.form.get('service_type')
        experience = request.form.get('experience')
        service_price = request.form.get('service_price')
        about_me = request.form.get('about_me')

        

        try:
            with psycopg2.connect(**db_params) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO profiles (username, service_type, experience, service_price, about_me)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (current_user.username, service_type, experience, service_price, about_me))
                    conn.commit()

            flash('Profile information saved successfully', 'success')
            return redirect(url_for('login'))  # Замените 'some_other_route' на маршрут, куда вы хотите перенаправить после сохранения профиля
        except psycopg2.Error as e:
            print(f"Database error: {e}")
            flash('error')

    return render_template('profiles_form.html')

def get_profile_by_username(username):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM profiles WHERE username = %s', (username,))
            return cursor.fetchone()

# Маршрут для редактирования анкеты
@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
  # Проверка, залогинен ли пользователь
    if 'username' not in session:
        flash('Для доступа к этой странице войдите в аккаунт', 'error')
        return redirect(url_for('login'))
    
    username = session['username']

    if request.method == 'POST':
        new_service_type = request.form.get('new_service_type')
        new_experience = request.form.get('new_experience')
        new_service_price = request.form.get('new_service_price')
        new_about_me = request.form.get('new_about_me')

        # Обновляем данные в базе данных, включая новый путь к фото
        update_profile(username, new_service_type, new_experience, new_service_price, new_about_me)

        flash('Данные анкеты успешно обновлены', 'success')
        return redirect(url_for('main'))
 

    # Если запрос GET, отображаем форму редактирования
    current_profile = get_profile_by_username(username)
    return render_template('edit_profile.html', current_profile=current_profile)


def update_profile(username, new_service_type, new_experience, new_service_price, new_about_me):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            # Проверяем, есть ли уже анкета для данного пользователя
            cursor.execute('SELECT * FROM profiles WHERE username = %s', (username,))
            existing_anketa = cursor.fetchone()

            if existing_anketa:
                # Если анкета уже существует, обновляем данные
                cursor.execute('''
                    UPDATE profiles 
                    SET service_type = %s, experience = %s, service_price = %s, about_me = %s
                    WHERE username = %s
                ''', (new_service_type, new_experience, new_service_price, new_about_me, username))
            else:
                # Если анкеты нет, добавляем новую
                cursor.execute('''
                    INSERT INTO Questionary (username, service_type, experience, service_price, about_me)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (username, new_service_type, new_experience, new_service_price, new_about_me))

        conn.commit()


@app.route('/hide_profiles', methods=['GET', 'POST'])
def hide_profiles():
    # Проверка, залогинен ли пользователь
    if 'username' not in session:
        flash('Для доступа к этой странице войдите в аккаунт', 'error')
        return redirect(url_for('login'))

    username = session['username']

    if request.method == 'POST':
        # Логика изменения статуса видимости анкеты
        set_profile_visibility(username, False)  # Устанавливаем статус видимости в False
        flash('Анкета успешно скрыта', 'success')
        return redirect(url_for('main'))

    return render_template('hide_profiles.html', username=username)

# Функция для установки статуса видимости анкеты
def set_profile_visibility(username, is_visible):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute('UPDATE profiles SET is_visible = %s WHERE username = %s', (is_visible, username))
        conn.commit()


# Функция для удаления пользователя из базы данных
def delete_user(username):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            # Удаление пользователя из таблицы users
            cursor.execute('DELETE FROM users WHERE username = %s', (username,))

            # Удаление связанных данных из других таблиц, например, questionary
            cursor.execute('DELETE FROM profiles WHERE username = %s', (username,))
            # Добавьте другие таблицы, если необходимо

# Роут для удаления аккаунта
@app.route('/delete_account', methods=['GET', 'POST'])
def delete_account():
    # Проверка, залогинен ли пользователь
    if 'username' not in session:
        flash('Для доступа к этой странице войдите в аккаунт', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Получаем имя пользователя из сессии
        username = session['username']

        # Удаление пользователя из базы данных
        delete_user(username)

        # Очистка сессии и перенаправление на главную страницу
        session.clear()
        flash('Ваш аккаунт успешно удален', 'success')
        return redirect(url_for('index'))

    return render_template('delete_account.html')  
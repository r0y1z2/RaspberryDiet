# app.py
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import numpy as np
from ultralytics import YOLO  # 确保使用正确的导入
from PIL import Image

# 初始化Flask应用
app = Flask(__name__)
app.config.update(
    UPLOAD_FOLDER=os.path.join(os.getcwd(), 'uploads'),
    DATABASE=os.path.join(os.getcwd(), 'diet.db'),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2MB限制
    ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg'}
)

# 简易食物数据库（单位：千卡/100克）
FOOD_DB = {
    'apple': 52,
    'banana': 89,
    'rice': 130,
    'egg': 155,
    'chicken': 239,
    'bread': 265,
    'salad': 35,
    'noodles': 138
}

# 初始化YOLOv8模型
model = YOLO("models/yolov8n.pt")  # 确保模型文件路径正确

def init_db():
    """初始化数据库"""
    with sqlite3.connect(app.config['DATABASE']) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS records
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      filename TEXT NOT NULL,
                      food_name TEXT NOT NULL,
                      calories REAL NOT NULL,
                      date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

def allowed_file(filename):
    """检查文件扩展名是否合法"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# def process_image(image_data):
#     """处理上传的图像数据"""
#     image_array = np.frombuffer(image_data, np.uint8)
#     image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
#     return image

def mock_ai_recognition(image_path):
    """使用YOLOv8模型进行图像识别"""
    results = model(image_path)  # 进行检测
    detected_objects = []
    for result in results:
        boxes = result.boxes
        for box in boxes:
            cls = box.cls[0].item()
            name = result.names[cls]  # 获取检测到的物体名称
            detected_objects.append(name)
    
    # 这里假设你只关心第一个检测到的对象
    if detected_objects:
        return detected_objects[0]
    return None

def get_calories(food_name, weight=100):
    """获取食物热量"""
    return FOOD_DB.get(food_name.lower(), 0) * (weight / 100)

def clean_old_files(days=7):
    """清理过期文件和记录"""
    expire_date = datetime.now() - timedelta(days=days)
    
    with sqlite3.connect(app.config['DATABASE']) as conn:
        # 获取过期记录
        cursor = conn.execute(
            "SELECT filename FROM records WHERE date < ?",
            (expire_date.strftime('%Y-%m-%d %H:%M:%S'),)
        )
        old_files = [row[0] for row in cursor.fetchall()]
        
        # 删除文件
        for filename in old_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"删除文件失败: {e}")
        
        # 删除数据库记录
        conn.execute(
            "DELETE FROM records WHERE date < ?",
            (expire_date.strftime('%Y-%m-%d %H:%M:%S'),)
        )
        conn.commit()

@app.route('/', methods=['GET', 'POST'])
def index():
    """主页路由"""
    if request.method == 'POST':
        # 处理文件上传
        if 'photo' not in request.files:
            return redirect(request.url)
        
        file = request.files['photo']
        if file.filename == '':
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            try:
                # 保存文件
                filename = secure_filename(file.filename)
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                
                # 获取食物信息
                weight = float(request.form.get('weight', 100))
                food_name = mock_ai_recognition(save_path)
                #calories = get_calories(food_name, weight)
                calories = 100
                
                # 写入数据库
                with sqlite3.connect(app.config['DATABASE']) as conn:
                    conn.execute(
                        "INSERT INTO records (filename, food_name, calories) VALUES (?, ?, ?)",
                        (filename, food_name, calories)
                    )
                    conn.commit()
                
            except Exception as e:
                print(f"处理上传时出错: {e}")
                return render_template('error.html', message="文件处理失败")

    # 获取数据展示
    with sqlite3.connect(app.config['DATABASE']) as conn:
        # 当日总热量
        daily_total = conn.execute(
            "SELECT SUM(calories) FROM records WHERE DATE(date) = DATE('now')"
        ).fetchone()[0] or 0
        
        # 所有记录（按时间倒序）
        records = conn.execute(
            "SELECT filename, food_name, calories, strftime('%Y-%m-%d %H:%M', date) as fmt_date "
            "FROM records ORDER BY date DESC"
        ).fetchall()
    
    return render_template(
        'index.html',
        daily_total=round(daily_total, 1),
        records=[dict(zip(['filename', 'food', 'calories', 'time'], row)) for row in records]
    )

@app.route('/uploads/<filename>')
def serve_file(filename):
    """提供上传文件访问"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.errorhandler(413)
def request_entity_too_large(error):
    """处理文件过大错误"""
    return render_template('error.html', message="文件大小超过2MB限制"), 413

if __name__ == '__main__':
    # 初始化目录和数据库
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    clean_old_files()
    
    # 启动应用
    app.run(
        host='0.0.0.0', 
        port=5000, 
        debug=True,
        threaded=True  # 启用多线程处理并发请求
    )

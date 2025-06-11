# app.py
from flask import Flask, render_template, request, redirect, url_for
import os
from werkzeug.utils import secure_filename
import sqlite3
#from config import API_KEY  # 创建config.py存放API密钥

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 限制2MB

# 简易食物数据库（单位：千卡/100克）
FOOD_DB = {
    'apple': 52,
    'banana': 89,
    'rice': 130,
    'egg': 155,
    'chicken': 239,
    'bread': 265
}

def init_db():
    conn = sqlite3.connect('diet.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT,
                  food_name TEXT,
                  calories REAL,
                  date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_daily_limit():
    """默认每日2000大卡，实际可扩展用户系统"""
    return 2000

def mock_ai_recognition(image_path):
    """模拟AI识别（实际应接入API）"""
    # 示例伪代码：
    # from baidu_aip import AipImageClassify
    # client = AipImageClassify(API_KEY)
    # with open(image_path, 'rb') as f:
    #     result = client.dishDetect(f.read())
    # return result['result'][0]['name']
    
    # 临时返回固定值供演示
    return 'apple'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['photo']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            
            # 食物识别
            food_name = mock_ai_recognition(save_path)
            weight = float(request.form.get('weight', 100))  # 默认100克
            
            # 计算卡路里
            calories = FOOD_DB.get(food_name, 0) * (weight/100)
            
            # 存入数据库
            conn = sqlite3.connect('diet.db')
            c = conn.cursor()
            c.execute("INSERT INTO records (filename, food_name, calories) VALUES (?,?,?)",
                     (filename, food_name, calories))
            conn.commit()
            conn.close()
            
            # 计算剩余可摄入量
            daily_limit = get_daily_limit()
            consumed = sum_record_calories()
            remaining = max(daily_limit - consumed, 0)
            
            return render_template('result.html', 
                                food=food_name,
                                calories=round(calories,1),
                                remaining=round(remaining,1))
    
    consumed = sum_record_calories()
    return render_template('upload.html', consumed=consumed)

def sum_record_calories():
    conn = sqlite3.connect('diet.db')
    c = conn.cursor()
    c.execute("SELECT SUM(calories) FROM records WHERE date(date) = date('now')")
    total = c.fetchone()[0] or 0
    conn.close()
    return total

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

if __name__ == '__main__':
    init_db()
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='0.0.0.0', port=5000, debug=True)

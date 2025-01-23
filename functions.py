import sqlite3
import os
import re
import pandas as pd

# 定义班级映射
class_mapping = {'A': 1, 'B': 2, 'C': 3, 'D': 4}
inverse_class_mapping = {v: k for k, v in class_mapping.items()}

def initialize_source_database(csv_file="merged_data.csv", db_file="course.db"):
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file '{csv_file}' not found.")

    df = pd.read_csv(csv_file, encoding='ISO-8859-1')
    conn = sqlite3.connect(db_file)
    df.to_sql("course", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    
initialize_source_database()

def initialize_database(course_list):
    # 创建并连接到 SQLite 数据库
    conn = sqlite3.connect('course_selection.db')
    cursor = conn.cursor()
    
    cursor.execute("ATTACH DATABASE 'course.db' AS course_db")

    # 创建 students 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            stream TEXT DEFAULT NULL
        )
    ''')
    # 插入学生数据
    students = [
        ('student1', 'password1'),
        ('student2', 'password2'),
        ('student3', 'password3'),
        ('student4', 'password4'),
        ('student5', 'password5')
    ]
    cursor.executemany('INSERT OR IGNORE INTO students (student_id, password) VALUES (?, ?)', students)

 # 创建 courses 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            course_id TEXT PRIMARY KEY
        )
    ''')
    
    # 从 merged_data.csv 中读取课程列表
    courses_tuples = [(course_id,) for course_id in course_list]
    cursor.executemany('INSERT OR IGNORE INTO courses (course_id) VALUES (?)', courses_tuples)

    # 创建 classes 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            course_id TEXT NOT NULL,
            class_number INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            PRIMARY KEY (course_id, class_number),
            FOREIGN KEY(course_id) REFERENCES courses(course_id)
        )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS moduless (
        modulenum TEXT NOT NULL,
        courses TEXT NOT NULL,
        timegap TEXT NOT NULL,
        PRIMARY KEY (modulenum)
    );
''')
    
    #创建 stream_requirements 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stream_requirements (
            stream TEXT NOT NULL,
            group_number INTEGER NOT NULL,
            course_id TEXT NOT NULL,
            PRIMARY KEY (stream, group_number, course_id)
        )
    ''')
    
     # **从csv 文件中读取stream信息**
    stream2 = pd.read_csv('stream_data.csv')

    # 准备插入 module表的数据
    stream1 = []

    stream= list(stream2.iloc[:,0])
    group_number = list(stream2.iloc[:,1])
    course_haha =list(stream2.iloc[:,2])

    for i in range(len(stream)):
        stream1.append((stream[i],group_number[i],course_haha[i]))
        
    cursor.executemany('''
                INSERT OR IGNORE INTO stream_requirements (stream, group_number, course_id)
                VALUES (?, ?, ?)
            ''', stream1)

    
    # **从csv 文件中读取班级信息**
    class_df = pd.read_csv('Module_course.csv')

    # 准备插入 classes 表的数据
    module_tuples = []

    modulenum = list(class_df.iloc[:,0])
    courses = list(class_df.iloc[:,1])
    timegap =list(class_df.iloc[:,2])

    for i in range(len(modulenum)):
        module_tuples.append((modulenum[i],courses[i],timegap[i]))
        
    cursor.executemany('''
            INSERT OR IGNORE INTO moduless (modulenum, courses, timegap)
            VALUES (?, ?, ?)
        ''', module_tuples)

    # **从 Course_class.csv 文件中读取班级信息**
    class_df = pd.read_csv('Course_class.csv')


    # 准备插入 classes 表的数据
    classes_tuples = []

    course_id = list(class_df.iloc[:,0])
    class_number = list(class_df.iloc[:,1])
    capacity =list(class_df.iloc[:,2])

    for i in range(len(course_id)):
        classes_tuples.append((course_id[i], class_number[i], capacity[i]))
    
    cursor.executemany('''
        INSERT OR IGNORE INTO classes (course_id, class_number, capacity)
        VALUES (?, ?, ?)
    ''', classes_tuples)
    
    # 创建 course_selection 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_selection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_id TEXT NOT NULL,
            class_number INTEGER NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id),
            FOREIGN KEY(course_id) REFERENCES courses(course_id),
            UNIQUE(student_id, course_id)  
        )
    ''')

    # 创建 waiting_queue 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS waiting_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_id TEXT NOT NULL,
            class_number INTEGER NOT NULL,
            position INTEGER NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id),
            FOREIGN KEY(course_id) REFERENCES courses(course_id),
            UNIQUE(student_id, course_id)  
        )
    ''')

    conn.commit()
    # 确保这里有 return 语句
    return conn, cursor


# 认证学生登录函数
def authenticate_student(cursor, student_id, password):
    conn = sqlite3.connect('course_selection.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM students WHERE student_id = ? AND password = ?
    ''', (student_id, password))
    if cursor.fetchone():
        return True
    else:
        return False


# 选择课程函数
def select_course(cursor, conn, student_id, course_id, class_letter):
    # 检查学生已选课程数量
    cursor.execute('''
        SELECT COUNT(DISTINCT course_id) FROM course_selection
        WHERE student_id = ?
    ''', (student_id,))
    course_count = cursor.fetchone()[0]
    if course_count >= 10:
        return "You have already selected 10 courses; you cannot select more courses."

    class_number = class_mapping.get(class_letter.upper())
    if not class_number:
        return f"Class {class_letter} does not exist. Please enter A, B, C, or D."

    # 检查班级是否存在
    cursor.execute('''
        SELECT capacity FROM classes WHERE course_id = ? AND class_number = ?
    ''', (course_id, class_number))
    result = cursor.fetchone()
    if not result:
        return f"Class {class_letter} of course {course_id} does not exist."
    capacity = result[0]

    # 获取班级当前人数
    cursor.execute('''
        SELECT COUNT(*) FROM course_selection
        WHERE course_id = ? AND class_number = ?
    ''', (course_id, class_number))
    current_count = cursor.fetchone()[0]

    # 检查学生是否已选该课程
    cursor.execute('''
        SELECT * FROM course_selection
        WHERE student_id = ? AND course_id = ?
    ''', (student_id, course_id))
    if cursor.fetchone():
        return f"You have already selected course {course_id}; you cannot select it again."

    # 检查学生是否在等待队列中
    cursor.execute('''
        SELECT * FROM waiting_queue
        WHERE student_id = ? AND course_id = ? AND class_number = ?
    ''', (student_id, course_id, class_number))
    if cursor.fetchone():
        return f"You are already in the waiting queue for class {class_letter} of course {course_id}."

    if current_count >= capacity:
        # 班级已满，返回一个特殊消息，提示学生选择是否加入等待队列
        return {
            "status": "CLASS_FULL",
            "message": f"Class {class_letter} of course {course_id} is full. Do you want to join the waiting queue?"
        }
    else:
        # 插入选课记录
        cursor.execute('''
            INSERT INTO course_selection (student_id, course_id, class_number)
            VALUES (?, ?, ?)
        ''', (student_id, course_id, class_number))
        conn.commit()
        return f"You have successfully selected class {class_letter} of course {course_id}."

# 加入等待队列函数
def join_waiting_queue(cursor, conn, student_id, course_id, class_letter):
    class_number = class_mapping.get(class_letter.upper())
    if not class_number:
        return f"Class {class_letter} does not exist."

    # 检查班级是否存在
    cursor.execute('''
        SELECT capacity FROM classes WHERE course_id = ? AND class_number = ?
    ''', (course_id, class_number))
    if not cursor.fetchone():
        return f"Class {class_letter} of course {course_id} does not exist."

    # 检查学生是否已在等待队列中
    cursor.execute('''
        SELECT * FROM waiting_queue
        WHERE student_id = ? AND course_id = ? AND class_number = ?
    ''', (student_id, course_id, class_number))
    if cursor.fetchone():
        return f"You are already in the waiting queue for class {class_letter} of course {course_id}."

    # 获取等待队列中最大位置
    cursor.execute('''
        SELECT MAX(position) FROM waiting_queue
        WHERE course_id = ? AND class_number = ?
    ''', (course_id, class_number))
    max_position = cursor.fetchone()[0]
    if max_position is None:
        position = 1
    else:
        position = max_position + 1

    # 插入到等待队列
    cursor.execute('''
        INSERT INTO waiting_queue (student_id, course_id, class_number, position)
        VALUES (?, ?, ?, ?)
    ''', (student_id, course_id, class_number, position))
    conn.commit()
    return f"You have been added to the waiting queue for class {class_letter} of course {course_id}. Your position is {position}."

# **取消等待队列函数**
def cancel_waiting(cursor, conn, student_id, course_id, class_letter):
    class_number = class_mapping.get(class_letter.upper())
    if not class_number:
        return f"Class {class_letter} does not exist."

    # 检查学生是否在等待队列中
    cursor.execute('''
        SELECT position FROM waiting_queue
        WHERE student_id = ? AND course_id = ? AND class_number = ?
    ''', (student_id, course_id, class_number))
    result = cursor.fetchone()
    if not result:
        return f"You are not in the waiting queue for class {class_letter} of course {course_id}; you cannot cancel it."

    position = result[0]

    # 删除等待队列记录
    cursor.execute('''
        DELETE FROM waiting_queue
        WHERE student_id = ? AND course_id = ? AND class_number = ?
    ''', (student_id, course_id, class_number))

    # 更新该班级等待队列中后续学生的排位
    cursor.execute('''
        UPDATE waiting_queue
        SET position = position - 1
        WHERE course_id = ? AND class_number = ? AND position > ?
    ''', (course_id, class_number, position))

    conn.commit()
    return f"You have been removed from the waiting queue for class {class_letter} of course {course_id}."

# **取消等待队列函数**
def cancel_waiting(cursor, conn, student_id, course_id, class_letter):
    class_number = class_mapping.get(class_letter.upper())
    if not class_number:
        return f"Class {class_letter} does not exist."

    # 检查学生是否在等待队列中
    cursor.execute('''
        SELECT position FROM waiting_queue
        WHERE student_id = ? AND course_id = ? AND class_number = ?
    ''', (student_id, course_id, class_number))
    result = cursor.fetchone()
    if not result:
        return f"You are not in the waiting queue for class {class_letter} of course {course_id}; you cannot cancel it."

    position = result[0]

    # 删除等待队列记录
    cursor.execute('''
        DELETE FROM waiting_queue
        WHERE student_id = ? AND course_id = ? AND class_number = ?
    ''', (student_id, course_id, class_number))

    # 更新该班级等待队列中后续学生的排位
    cursor.execute('''
        UPDATE waiting_queue
        SET position = position - 1
        WHERE course_id = ? AND class_number = ? AND position > ?
    ''', (course_id, class_number, position))

    conn.commit()
    return f"You have been removed from the waiting queue for class {class_letter} of course {course_id}."

# 退课函数
def drop_course(cursor, conn, student_id, course_id, class_letter=None):
    conn = sqlite3.connect('course_selection.db')
    cursor = conn.cursor()
    # 检查学生是否已选该课程
    cursor.execute('''
        SELECT class_number FROM course_selection
        WHERE student_id = ? AND course_id = ?
    ''', (student_id, course_id))
    selection = cursor.fetchone()
    if not selection:
        return f"You have not selected course {course_id}; you cannot drop it."

    class_number = selection[0]

    # 删除选课记录
    cursor.execute('''
        DELETE FROM course_selection
        WHERE student_id = ? AND course_id = ?
    ''', (student_id, course_id))
    conn.commit()

    # 检查等待队列
    cursor.execute('''
        SELECT student_id FROM waiting_queue
        WHERE course_id = ? AND class_number = ?
        ORDER BY position ASC
        LIMIT 1
    ''', (course_id, class_number))
    waiting_student = cursor.fetchone()
    if waiting_student:
        waiting_student_id = waiting_student[0]
        # 从等待队列中移除学生
        cursor.execute('''
            DELETE FROM waiting_queue
            WHERE student_id = ? AND course_id = ? AND class_number = ?
        ''', (waiting_student_id, course_id, class_number))
        # 将学生加入选课记录
        cursor.execute('''
            INSERT INTO course_selection (student_id, course_id, class_number)
            VALUES (?, ?, ?)
        ''', (waiting_student_id, course_id, class_number))
        conn.commit()
        # 通知学生已被加入课程（可以在实际系统中实现通知功能）
        return f"You have successfully dropped course {course_id}. Student {waiting_student_id} has been moved from the waiting queue to class {inverse_class_mapping[class_number]} of course {course_id}."
    else:
        return f"You have successfully dropped course {course_id}."

# 查询已选课程函数
def query_selected_courses(cursor, student_id):
    cursor.execute('''
        SELECT course_id, class_number FROM course_selection
        WHERE student_id = ?
    ''', (student_id,))
    results = cursor.fetchall()
    if results:
        course_list = []
        for course_id, class_number in results:
            class_letter = inverse_class_mapping.get(class_number, 'Unknown')
            course_list.append(f"Course {course_id} Class {class_letter}")
        return "Your selected courses are: " + ", ".join(course_list) + "."
    else:
        return "You have not selected any courses yet."
    
# 需要返回课程list

# 查看专业方向函数
def view_stream(cursor, student_id):
    conn = sqlite3.connect('course_selection.db')
    cursor = conn.cursor()
    cursor.execute('SELECT stream FROM students WHERE student_id = ?', (student_id,))
    result = cursor.fetchone()
    if result:
        stream = result[0]
        if stream:
            return f"Your current stream is '{stream}'."
        else:
            return "You have not selected a stream yet."
    else:
        return "Student not found."
    
def get_stream_courses(cursor,stream: str) -> str:
    from collections import defaultdict
    conn = sqlite3.connect('course_selection.db')
    cursor = conn.cursor()
    stream_lower = stream.strip().lower()

    # 查询该流的所有课程分组
    cursor.execute('''
        SELECT group_number, course_id
        FROM stream_requirements
        WHERE stream = ?
        ORDER BY group_number, course_id
    ''', (stream_lower,))
    
    results = cursor.fetchall()

    if not results:
        conn.close()
        return f"The stream '{stream}' is not recognized."

    # 使用 defaultdict 按 group_number 分组课程
    course_groups = defaultdict(list)

    for group_number, course_id in results:
        course_groups[group_number].append(course_id)

    # 构建输出字符串
    info_lines = [
        f"Group {group_number}: {', '.join(sorted(courses))}"
        for group_number, courses in sorted(course_groups.items())
    ]

    # 添加选择要求的信息
    selection_requirement = "You must select at least one course from each group."

    info_text = (
        f"Here are the course groups for the '{stream}' stream:\n"
        + "\n".join(info_lines)
        + "\n\n" + selection_requirement
    )

    return info_text


# 修改专业方向函数
def modify_stream(cursor, conn, student_id, new_stream):
    conn = sqlite3.connect('course_selection.db')
    cursor = conn.cursor()
    valid_streams = ['AI', 'MC', None]
    if new_stream not in valid_streams:
        return "Invalid stream. Please choose 'AI', 'MC', or None."

    cursor.execute('UPDATE students SET stream = ? WHERE student_id = ?', (new_stream, student_id))
    conn.commit()
    if new_stream:
        return f"Your stream has been updated to '{new_stream}'."
    else:
        return "You have removed your stream selection."

# 验证专业方向要求函数
def validate_stream_requirements(cursor,student_id):
    stream_requirements = {
    
        'ai': [
            {'7013', '7027', '7028'},
            {'7026', '7033', '7035', '7036'}
        ],
        'mc': [
            {'7024', '7028','7029','7025','7023','7014'},
            {'7012', '7016','7017','7030'}
        ]
    }
    
    conn = sqlite3.connect('course_selection.db')
    cursor = conn.cursor()
    cursor.execute('SELECT stream FROM students WHERE student_id = ?', (student_id,))
    result = cursor.fetchone()
    
    if not result:
        return "Student not found."
    
    stream = result[0]  # 学生所选的流
    if not stream or stream.lower() == 'none':
        # 如果学生没有选择任何流，无需验证
        return "You have not selected a stream, so there are no requirements to validate."
    
    # 3. 获取学生已经选择的课程
    cursor.execute('''
        SELECT course_id FROM course_selection
        WHERE student_id = ?
    ''', (student_id,))
    selected_courses = set(course_id for (course_id,) in cursor.fetchall())

    stream_lower = stream.lower()

    # 4. 根据 stream_lower 判断是否在 stream_requirements 中
    if stream_lower in stream_requirements:
        required_course_groups = stream_requirements[stream_lower]
        
        # 用于记录哪些分组尚未满足
        missing_requirements = []
        
        # 逐一检查每个分组
        for group in required_course_groups:
            # 如果该分组与学生已选课程没有交集，则表示该分组未满足
            if not (selected_courses & group):
                # 把该分组需要的所有课程都列出来，方便学生对照
                missing_requirements.append(', '.join(sorted(group)))
        
        # 如果 missing_requirements 为空，则说明每一组都至少选了一门
        if not missing_requirements:
            return f"Your selected courses meet the requirements for the '{stream}' stream."
        else:
            # 拼装提示信息，让学生知道需要再选哪些分组的课程
            # 例如： "You need to select at least one of the following courses: 7005, 7006 and at least one of the following courses: 7013, 7027"
            missing_message = " and ".join(
                [f"at least one of the following courses: {grp}" for grp in missing_requirements]
            )
            return (f"You do not meet the requirements for the '{stream}' stream. "
                    f"You need to select {missing_message}.")
    else:
        # 如果 stream 不在我们定义的 stream_requirements 中，视为无法识别
        return "Your stream is unrecognized, so no requirements can be validated."
    
def query_waiting_courses(cursor, student_id):
    cursor.execute('''
        SELECT course_id, class_number, position FROM waiting_queue
        WHERE student_id = ?
        ORDER BY course_id, class_number
    ''', (student_id,))
    results = cursor.fetchall()
    if results:
        waiting_list = []
        for course_id, class_number, position in results:
            class_letter = inverse_class_mapping.get(class_number, 'Unknown')
            waiting_list.append(f"Course {course_id} Class {class_letter} (Position {position})")
        return "You are currently in the waiting queue for: " + ", ".join(waiting_list) + "."
    else:
        return "You are not in any waiting queues."
    

def count_waiting_queue(cursor, student_id,course_id, class_letter):
    class_number = class_mapping.get(class_letter.upper())
    if not class_number:
        return f"Class {class_letter} does not exist. Please enter A, B, C, or D."
    
    # 检查班级是否存在
    cursor.execute('''
        SELECT capacity FROM classes WHERE course_id = ? AND class_number = ?
    ''', (course_id, class_number))
    if not cursor.fetchone():
        return f"Class {class_letter} of course {course_id} does not exist."
    
    # 查询等待队列中的学生
    cursor.execute('''
        SELECT student_id, position FROM waiting_queue
        WHERE course_id = ? AND class_number = ?
        ORDER BY position ASC
    ''', (course_id, class_number))
    results = cursor.fetchall()
    if results:
        waiting_students = []
        for student_id, position in results:
            waiting_students.append(f"Student {student_id} (Position {position})")
        count = len(results)
        return f"There are {count} students in the waiting queue for class {class_letter} of course {course_id}: " + ", ".join(waiting_students) + "."
    else:
        return f"There are no students in the waiting queue for class {class_letter} of course {course_id}."
    
    
def advanced_course_query(
    cursor,
    Extracted_Information=None,
    CourseCode=None,
    CourseName=None,
    Module_and_Period=None,
    Course_Code_and_Title=None,
    Course_Type=None,
    Instructor=None,
    Tutorial_Group=None,
    Tutorial_Dates_and_Time_and_Tutorial_Venue=None,
    Exam_or_Final_project_Date_Time_and_Venue=None,
    CombinedClassInformation=None
):
    """
    Allows the user to query course information based on any combination of fields.
    If the query does not find any results, returns 'Not Found'.

    Parameters:
        cursor (sqlite3.Cursor): The database cursor.

        Extracted_Information (str, optional): Extracted information from the course details.
        CourseCode (str, optional): The code of the course.
        CourseName (str, optional): The name of the course.
        Module_and_Period (str, optional): The module and period of the course.
        Course_Code_and_Title (str, optional): Combined course code and title.
        Course_Type (str, optional): The type of the course.
        Instructor (str, optional): The instructor teaching the course.
        Tutorial_Group (str, optional): The tutorial group information.
        Tutorial_Dates_and_Time_and_Tutorial_Venue (str, optional): Tutorial dates, times, and venue.
        Exam_or_Final_project_Date_Time_and_Venue (str, optional): Exam or final project date, time, and venue.
        CombinedClassInformation (str, optional): Combined class information.

    Returns:
        str: The formatted results of the query, or 'Not Found' if no results are found.
    """
    # 定义参数名到数据库字段名的映射
    field_mapping = {
        'Extracted_Information': 'ExtractedInformation',
        'CourseCode': 'CourseCode',
        'CourseName': 'CourseName',
        'Module_and_Period': 'Module',
        'Course_Code_and_Title': 'CourseCode_and_Title',
        'Course_Type': 'CourseType',
        'Instructor': 'Instructor',
        'Tutorial_Group': 'Tutorial_Group',
        'Tutorial_Dates_and_Time_and_Tutorial_Venue': 'Turorialtime	',
        'Exam_or_Final_project_Date_Time_and_Venue': 'Final',
        'CombinedClassInformation': 'CombinedClassInformation'
    }

    # 构建SQL查询语句
    sql_query = "SELECT * FROM course_db.course"
    conditions = []
    values = []

    # 构建查询条件
    for param_name, field_name in field_mapping.items():
        param_value = locals()[param_name]  # 获取参数的值
        if param_value is not None:
            conditions.append(f"`{field_name}` LIKE ?")
            values.append(f"%{param_value}%")

    # 如果没有提供任何参数，则返回提示信息
    if not conditions:
        return "No query parameters provided."

    # 添加WHERE子句
    if conditions:
        sql_query += " WHERE " + " AND ".join(conditions)

    # 执行查询
    cursor.execute(sql_query, values)
    results = cursor.fetchall()

    if results:
        # 获取列名
        column_names = [description[0] for description in cursor.description]
        # 格式化结果
        formatted_results = []
        for row in results:
            row_dict = dict(zip(column_names, row))
            formatted_row = '\n'.join([f"{key}: {value}" for key, value in row_dict.items()])
            formatted_results.append(formatted_row)
        return '\n\n'.join(formatted_results)
    else:
        return "Not Found."
    
    
def get_courses_by_module(cursor, module_query):
    """
    根据模块查询信息（支持模糊匹配）查询其包含的课程。

    参数：
        cursor (sqlite3.Cursor): 数据库游标。
        module_query (str): 模块查询信息，可以是模块编号或部分名称。

    返回：
        str: 包含的课程列表或提示信息。
    """
    cursor.execute('SELECT modulenum, courses FROM moduless')
    modules = cursor.fetchall()

    matches = []
    for modulenum, courses in modules:
        if module_query.lower() in modulenum.lower():
            course_list = [course.strip() for course in courses.split(',')]
            matches.append((modulenum, course_list))

    if matches:
        results = []
        for modulenum, course_list in matches:
            results.append(f"Module {modulenum} contains the following courses: {', '.join(course_list)}.")
        return '\n'.join(results)
    else:
        return f"No module matching '{module_query}' found."
    
def parse_class_times(combined_info, class_letter):
    """
    从 CombinedClassInformation 中解析班级时间信息，返回时段列表，如：
    [('Monday', 9.5, 12.5), ('Thursday', 9.5, 12.5)]
    """
    pattern = r"([ABCD]):([\s\S]*?)(?=[ABCD]:|$)"
    matches = re.findall(pattern, combined_info)
    for m_class_letter, m_block in matches:
        if m_class_letter.strip().upper() == class_letter.upper():
            lines = m_block.strip().split("\n")
            if len(lines) < 2:
                return []
            days_line = lines[0]  # 如 "Monday & Thursday"
            time_line = lines[1]  # 如 "9:30-12:30"

            days = [d.strip() for d in days_line.split("&")]
            start_end = time_line.split("-")
            if len(start_end) != 2:
                return []

            def parse_time_str(t):
                h, m = t.split(":")
                return float(h) + float(m) / 60

            start_time = parse_time_str(start_end[0].strip())
            end_time = parse_time_str(start_end[1].strip())

            slots = []
            for day in days:
                day = day.strip()
                if day:
                    slots.append((day, start_time, end_time))
            return slots
    return []

def check_conflict(slot_a, slot_b):
    """
    检查两门课的日程slot是否冲突：
    slot_a 形如 ('Monday', 9.5, 12.5)
    slot_b 形如 ('Monday', 10.0, 13.0)
    """
    day_a, start_a, end_a = slot_a
    day_b, start_b, end_b = slot_b
    # 同一天并且时间区间有交集即视为冲突
    if day_a.lower() == day_b.lower():
        return not (end_a <= start_b or end_b <= start_a)
    return False

def check_time_conflict_for_new_selection(cursor, student_id, new_course_id, new_class_letter):
    """
    从数据库中读取学生已选的所有课程，然后与新选课程时间做比对，如果有冲突返回提示。
    """
    # 已选课程列表
    conn = sqlite3.connect('course_selection.db')
    cursor = conn.cursor()
    c_conn = sqlite3.connect('course.db')
    c_cursor = c_conn.cursor()
    c_cursor.execute("ATTACH DATABASE 'course.db' AS course_db")
    
    cursor.execute('SELECT course_id, class_number FROM course_selection WHERE student_id = ?', (student_id,))
    selected = cursor.fetchall()
        # 若学生未选课程，直接返回无冲突
    if not selected:
        return (False, "You have no existing courses; no conflict detected.")
    
    # 获取新课程 CombinedClassInformation
    c_cursor.execute('SELECT `CombinedClassInformation` FROM course_db.course WHERE `CourseCode` LIKE ?', (f"%{new_course_id}%",))
    new_row = c_cursor.fetchone()
    
    # 获取新课程所属 module
    c_cursor.execute('SELECT `Module` FROM course_db.course WHERE `CourseCode` LIKE ?', (f"%{new_course_id}%",))
    new_module_row = c_cursor.fetchone()
    new_module = new_module_row[0] if new_module_row else None
    
    if not new_row:
        return (False, f"Course {new_course_id} not found in course_db.")
    try:
        new_slots = parse_class_times(new_row[0], new_class_letter)
    except ValueError as e:
        return (False, str(e))
    
    # 与已选课程进行时间冲突比对
    for course_id, class_number in selected:
        # 获取已选课程所属 module
        c_cursor.execute('SELECT `Module` FROM course_db.course WHERE `CourseCode` LIKE ?', (f"%{course_id}%",))
        exist_module_row = c_cursor.fetchone()
        exist_module = exist_module_row[0] if exist_module_row else None
        if new_module and exist_module and new_module == exist_module:
            exist_letter = next((k for k, v in class_mapping.items() if v == class_number), None)
            c_cursor.execute('SELECT `CombinedClassInformation` FROM course_db.course WHERE `CourseCode` LIKE ?', (f"%{course_id}%",))
            exist_row = c_cursor.fetchone()
            if not exist_row:
                continue
            exist_slots = parse_class_times(exist_row[0], exist_letter)
            for ns in new_slots:
                for es in exist_slots:
                    if check_conflict(ns, es):
                        return (True, f"Time conflict with your existing course {course_id} Class {exist_letter}.")
    return (False, "No time conflict.")

def check_courses_mutual_conflict(cursor, course_list):
    """
    若用户一次查询(或选择)多个课程，从数据库中获取各课的 CombinedClassInformation，
    解析后互相检测冲突。
    course_list = [(course_id, class_letter), (course_id, class_letter), ...]
    """
    c_conn = sqlite3.connect('course.db')
    c_cursor = c_conn.cursor()
    c_cursor.execute("ATTACH DATABASE 'course.db' AS course_db")
    parsed_data = []
    conflict_pairs = {('7037', '7025'), ('7025', '7037')}
    # 检查互斥课程对
    course_ids = [cid for cid, _ in course_list]
    for pair in conflict_pairs:
        if pair[0] in course_ids and pair[1] in course_ids:
            return (True, f"Courses {pair[0]} and {pair[1]} cannot be selected together.")
    
    for cid, cletter in course_list:
        c_cursor.execute('SELECT CombinedClassInformation FROM course_db.course WHERE CourseCode LIKE ?', (f"%{cid}%",))
        row = c_cursor.fetchone()
        if not row:
            # 如果课程不存在，直接忽略或可提示
            continue
        slots = parse_class_times(row[0], cletter)
        
        c_cursor.execute('SELECT Module FROM course_db.course WHERE CourseCode LIKE ?', (f"%{cid}%",))
        module_row = c_cursor.fetchone()
        module_val = module_row[0] if module_row else None
        
        parsed_data.append((cid, cletter, slots,module_val))

    # 两两比较
    for i in range(len(parsed_data)):
        for j in range(i + 1, len(parsed_data)):
            cid_a, cla_a, slots_a,mod_a = parsed_data[i]
            cid_b, cla_b, slots_b,mod_b = parsed_data[j]
            if mod_a and mod_b and (mod_a == mod_b):
                for sa in slots_a:
                    for sb in slots_b:
                        if check_conflict(sa, sb):
                            return (True, f"Courses {cid_a} Class {cla_a} and {cid_b} Class {cla_b} have time conflict.")
    return (False, "No conflict found.")

def check_option_conflict(cursor, student_id, new_course_id):
    """
    从数据库中获取学生已选课程，与自定义的 conflict_map 比对以判断选修冲突。
    例如可能某些课程互斥，如 ('7001', '7002')。
    """
    conflict_map = {
        ('7037', '7025'),
        ('7025', '7037')
    }
    conn = sqlite3.connect('course_selection.db')
    cursor = conn.cursor()
    # 获取学生已选课程
    cursor.execute('SELECT course_id FROM course_selection WHERE student_id = ?', (student_id,))
    selected = [row[0] for row in cursor.fetchall()]

    for sc in selected:
        if (sc, new_course_id) in conflict_map:
            return (True, f"Course {new_course_id} conflicts with your selected course {sc}. Cannot take both.")
    return (False, "No option conflict found.")

import json

def load_recommendations(json_file="recommendations.json"):
    """
    加载推荐数据的 JSON 文件。
    参数：
        json_file (str): JSON 文件路径。
    返回：
        dict: 加载的推荐数据。
    """
    with open(json_file, "r", encoding="utf-8") as file:
        return json.load(file)

def recommend_courses_based_on_scenario(cursor, scenario, sub_scenario=None, module=None):
    """
    获取特定场景的推荐信息。
    参数：
        json_data (dict): 推荐数据。
        scenario (str): 场景名称（如 "high_gpa"）。
        sub_scenario (str): 子场景名称（如 "algorithm_engineer_machine_learning_engineer"）。
        module (str): 模块编号（如 "module3"）。
    返回：
        dict 或 list: 推荐信息。
    """
    json_data = load_recommendations('recommendations.json')
    recommendations = json_data.get("recommendations", {})
    scenario_data = recommendations.get(scenario)

    if not scenario_data:
        return f"Scenario '{scenario}' not found."

    # 子场景处理
    if sub_scenario:
        scenario_data = scenario_data.get(sub_scenario)
        if not scenario_data:
            return f"Sub-scenario '{sub_scenario}' not found in scenario '{scenario}'."

    # 模块处理
    if module and "modules" in scenario_data:
        module_data = scenario_data["modules"].get(module)
        if not module_data:
            return f"Module '{module}' not found in scenario '{scenario}'."
        return module_data

    return scenario_data

def load_program_info():
    with open("program_info.json", "r") as f:
        return json.load(f)

def get_program_introduction(cursor,topic=None):
    """
    Fetch program introduction based on the specified topic.
    
    Args:
        topic (str): The specific topic to fetch (e.g., 'academic_structure', 'capstone').
    
    Returns:
        str: The introduction content.
    """
    program_info = load_program_info()
    if not topic:
        # 如果没有指定主题，返回所有内容
        response = "Program Overview:\n"
        for key, value in program_info["program_overview"].items():
            response += f"\n- {key.replace('_', ' ').capitalize()}:\n  " + "\n  ".join(value)
        return response
    
    # 根据主题查询
    topic_info = program_info["program_overview"].get(topic)
    if not topic_info:
        return f"Sorry, I don't have information about '{topic}'."
    
    response = f"{topic.replace('_', ' ').capitalize()}:\n" + "\n".join(topic_info)
    return response


import os
import io
import time
import json
import sqlite3
import logging
import traceback

from datetime import datetime
from typing import Iterable
from pathlib import Path

import streamlit as st
from openai import AzureOpenAI
from openai.types.beta.threads import Message, TextContentBlock, Run
from openai.types.beta.thread import Thread
from dotenv import load_dotenv

##########################
# page configuraion
st.set_page_config(
    page_title="MSBA Course Enrollment",
    page_icon=":books:",
    layout="centered",
    initial_sidebar_state="expanded"
)
##########################

def setup_logging():
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s',
                       handlers=[
                           logging.StreamHandler(),
                           logging.FileHandler('agent_logs.txt', mode='a')
                       ])
    return logging.getLogger(__name__)

logger = setup_logging()

# 导入业务逻辑函数
from functions import *

initialize_source_database()
df=pd.read_csv('merged_data.csv', encoding='ISO-8859-1')
course_list = df['CourseCode'].unique()
conn, cursor = initialize_database(course_list)

# 定义班级映射
class_mapping = {'A': 1, 'B': 2, 'C': 3, 'D': 4}
inverse_class_mapping = {v: k for k, v in class_mapping.items()}

# 加载环境变量
load_dotenv(".env")
api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")
api_deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# define Log in dialog content
@st.dialog("Log In")
def login():
    student_id = st.text_input("Student ID", key="uid")
    password = st.text_input("Password", key="password", type='password')
    if st.button("Submit"):
        if authenticate_student(cursor, student_id, password):
            st.success("Welcome!")
            st.session_state['logged_in'] = True
            st.session_state['student_id'] = student_id
            time.sleep(1)
            st.rerun()
        else:
            st.error("Incorrect account or password. Please try again.")

if "logged_in" not in st.session_state: # initial page before lag in
    
    st.image("head.png", use_container_width=True)
    st.write("")
    st.write("")
    st.write("")
    st.write("")

    col1, col2, col3 = st.columns(3, vertical_alignment="bottom")
    col1.write("")
    if col2.button("Log In to Start", use_container_width=True):
        login() # call function to open login dialog
    col3.write("")

    st.write("")
    st.write("")
    st.write("")
    st.write("")
    st.image("bg.png", use_container_width=True)
##########################

else: # load main page after log in   

    # 创建 AzureOpenAI 客户端
    client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=api_endpoint)
    instruction = (              
    "You are an advanced assistant designed to help students effectively manage their course selections. "
    "Your role includes performing actions such as checking conflict within courses, selecting courses, dropping courses, querying selected courses, "
    "viewing and modifying a student’s study stream, and validating stream requirements."
    "Follow the structured guidelines below to ensure students have a smooth course selection experience:\n\n"
    
    "### **Conflict Check Guidelines**\n"
    "1. **Single Course Selection**:\n"
    "When a student requests to add a new course, you must:\n"
    "- Check for time conflicts between the newly selected course and the already selected courses.\n"
    "- If a conflict exists:\n"
    "1. Clearly notify the student about the specific conflict, mentioning the conflicting courses and time slots.\n"
    "2. Stop the course addition process immediately.\n"
    "3. Suggest to ajust their select course, or provide an option to resolve conflicts, such as choosing another course or adjusting existing ones.\n"
    "For multiple course selections, you have to check whether there is a time conflict among multiple courses if users input mutiple courses. If any conflicts are found:\n"
    " 1. Notify the student about the conflicting courses and the specific time overlap.\n"
    " 2. Stop the addition process until conflicts are resolved.\n"
    
    "2. **Multiple Course Selection**:\n"
    "When a student requests to add multiple courses simultaneously:\n"
    "- Check for time conflicts among the input courses and between the input courses and already selected courses.\n"
    "- If any conflicts are found:\n"
     "1. Notify the student about all conflicts, specifying the conflicting courses and overlapping time slots.\n"
     "2. Stop the course addition process for all conflicting courses.\n"
     "3. Suggest to ajust their select course, or provide an option to resolve conflicts, such as choosing another course or adjusting existing ones.\n"

    "### **Additional Guidelines**\n"
    "- Always validate the selected course or class exists before performing a conflict check.\n"
    "- If a student requests an action that cannot be completed due to conflicts, guide them clearly and professionally to resolve the issue.\n"
    "- For any course addition requests, ensure to check:\n"
      "- Whether the course is already selected.\n"
      "- Whether the course is available (not full or invalid).\n"
      "- Whether it meets the stream requirements (if applicable).\n"
    "- Respond in a structured and clear manner to provide students with all necessary information for informed decision-making.\n"

    "**Key Responsibilities**:\n"
    "1. Course Selection and Conflict Checking:\n"
    "- When a student requests to add a course, you must:\n"
    "  - Check for time conflicts between the new course and the already selected courses.\n"
    "  - If a time conflict bewteen different courses exists, stop the selection process and notify the student about the conflict.\n"
    "    Example:\n"
    "      - Student Request: \"Add course 7013 A to my schedule.\"\n"
    "      - Your Response: \"Course 7013 A conflicts with your existing schedule (7027 A, Monday & Thursday 9:30-12:30). Please choose another course or adjust your schedule.\"\n"
    "  - If a course conflict (students cannot select two different courses together) exists, stop the selection process and notify the student about the conflict.\n"
    "    Example:\n"
    "      - Student Request: \"Add course 7025 A and 7037 A.\"\n"
    "      - Your Response: \"Courses 7025 A and 7037 A conflict together. You cannot select these two courses together. Please modify your selection.\"\n\n"
    "- For multiple course selections, verify if there is any time conflict and course confilct among the selected courses. If conflicts are detected:\n"
    "  - Stop the process.\n"
    "  - Notify the student and guide them to resolve the issue.\n"
    "    Example:\n"
    "      - Student Request: \"Add courses 7013A and 7027A.\"\n"
    "      - Your Response: \"Courses 7013 class A and 7027 class A conflict on Monday & Thursday 9:30-12:30. Please modify your selection.\"\n\n"

    "2. Dropping Courses:\n"
    "- When dropping a course, confirm the request and execute the action by calling the appropriate function.\n"
    "  Example:\n"
    "    - Student Request: \"Drop course 7001 A.\"\n"
    "    - Your Response: \"Course 7001 A has been successfully dropped from your schedule.\"\n\n"

    "3. Querying Courses:\n"
    "- For course information requests, follow this two-step approach:\n"
    "  1. Query all available course IDs and course names first.\n"
    "  2. Use the obtained course ID and course name to query detailed course information.\n"
    "  Example:\n"
    "    - Student Request: \"Provide details about 7001 A.\"\n"
    "    - Your Process:\n"
    "      1. Query all course IDs and names.\n"
    "      2. Query detailed information for 7001 A.\n"
    "    - Your Response: \"7001A: Introduction to ... .\"\n\n"

    "4. Study Stream Management:\n"
    "- Allow students to view or modify their study stream as requested.\n"
    "- Validate stream requirements when required to ensure compliance with academic guidelines.\n"
    "  Example:\n"
    "    - Student Request: \"Switch my stream to AI .\"\n"
    "    - Your Response: \"Your stream has been updated to AI stream. Please ensure you meet the stream requirements by completing the necessary courses.\"\n\n"
    
    "5. Waiting Queue Management:\n"
    "- Allow students to join or cancel the waiting queue for full courses.\n"
    "- Provide the number of students in the waiting queue for a specific course.\n"
    "  Example:\n"
    "    - Student Request: \"Join the waiting queue for course 7013 A.\"\n"
    "    - Your Response: \"You have successfully joined the waiting queue for course 7013 A.\"\n\n"
    
    "6. Senerio-based Course Recommendation:\n"
    "- Provide course recommendations based on specific scenarios, such as high GPA, career path, or internship.\n"
    "  Example:\n"
    "    - Student Request: \"Recommend courses for a high GPA scenario.\"\n"
    "    - Your Response: \"Based on your high GPA scenario, I recommend courses 7013 A, 7027 A, and 7037 A because ....\"\n\n"
    
    "7. Program Introduction:\n"
    "- Provide an overview or details about the academic structure, and other features of the program.\n"
    "  Example:\n"
    "    - Student Request: \"Tell me more about the Academic structure.\"\n"
    "    - Your Response: \"Our academic structure is ... .\"\n\n"
    
    "Operational Guidelines:\n"
    "1. Parameter Management:\n"
    "- Always provide the necessary parameters when calling functions.\n"
    "- If parameters are missing, ask the student for the required details.\n"
    "  Example:\n"
    "    - Missing Parameter: \"Please specify the course ID for the course you want to drop.\"\n\n"

    "2. ID Handling:\n"
    "- Do not request the student’s ID, as it is automatically available after login.\n\n"

    "3. Conflict Awareness:\n"
    "- Remind students to check potential time conflicts when selecting multiple courses.\n"
    "  Example:\n"
    "    - Student Request: \"Add courses 7013A and 7027A.\"\n"
    "    - Your Response: \"I’ll check for any scheduling conflicts before adding these courses.\"\n\n"

    "4. Error Prevention:\n"
    "- Ensure actions (e.g., course additions) are performed only when no conflicts or errors are present.\n\n"

    "Notes:\n"
    "- Always ensure clarity and professionalism in communication.\n"
    "- Follow a logical sequence when processing requests.\n"
    "- Prioritize user satisfaction by guiding students toward resolving conflicts or issues effectively."
)

    # 定义助手的工具列表（函数）
    tools_list = [
        {"type": "code_interpreter"},
        {
            "type": "function",
            "function": {
                "name": "select_course",
                "description": "Allows the student to select a course and enroll in a class.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "course_id": {"type": "string", "description": "The course ID to select."},
                        "class_letter": {"type": "string", "description": "The class letter (A, B, C, or D)."},
                    },
                    "required": ["course_id", "class_letter"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "drop_course",
                "description": "Allows the student to drop a previously selected course.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "course_id": {"type": "string", "description": "The course ID to select."},
                        "course_letter": {"type": "string", "description": "The class letter (A, B, C, or D)."},
                        
                    },
                    "required": ["course_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_selected_courses",
                "description": "Allows the student to query their selected courses.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "view_stream",
                "description": "Allows the student to view their current study stream.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "modify_stream",
                "description": "Allows the student to modify their study stream.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_stream": {"type": "string", "description": "The new study stream (AI, Business, or None)."},
                    },
                    "required": ["new_stream"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "validate_stream_requirements",
                "description": "Validates if the student meets the requirements of their study stream.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "join_waiting_queue",
                "description": "Allows the student to join the waiting queue for a full course.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "course_id": {"type": "string", "description": "The course ID to select."},
                        "class_letter": {"type": "string", "description": "The class letter (A, B, C, or D)."},
                    },
                    "required": ["course_id", "class_letter"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "cancel_waiting",
                "description": " Allows the student to cancel their waiting queue position.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "course_id": {"type": "string", "description": "The course ID to select."},
                        "class_letter": {"type": "string", "description": "The class letter (A, B, C, or D)."},
                    },
                    "required": ["course_id", "class_letter"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "count_waiting_queue",
                "description": "Counts the number of students in the waiting queue for a full course.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "course_id": {"type": "string", "description": "The course ID to select."},
                        "class_letter": {"type": "string", "description": "The class letter (A, B, C, or D)."},
                    },
                    "required": ["course_id", "class_letter"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_waiting_courses",
                "description": "Counts the number of students in the waiting queue for a full course.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
    {
        "type": "function",
        "function": {
            "name": "advanced_course_query",
            "description": "Allows the user to query course information based on any combination of fields in the course database. If the query does not find any results, returns 'Not Found'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "Extracted_Information": {
                        "type": "string",
                        "description": "Extracted information from the course details."
                    },
                    "CourseCode": {
                        "type": "string",
                        "description": "The code of the course."
                    },
                    "CourseName": {
                        "type": "string",
                        "description": "The name of the course."
                    },
                    "Module_and_Period": {
                        "type": "string",
                        "description": "The module and period of the course,if a student ask for module quesions,you shoud have this parameter."
                    },
                    "Course_Code_and_Title": {
                        "type": "string",
                        "description": "Combined course code and title."
                    },
                    "Course_Type": {
                        "type": "string",
                        "description": "The type of the course."
                    },
                    "Instructor": {
                        "type": "string",
                        "description": "The instructor teaching the course."
                    },
                    "Tutorial_Group": {
                        "type": "string",
                        "description": "The tutorial group information."
                    },
                    "Tutorial_Dates_and_Time_and_Tutorial_Venue": {
                        "type": "string",
                        "description": "Tutorial dates, times, and venue."
                    },
                    "Exam_or_Final_project_Date_Time_and_Venue": {
                        "type": "string",
                        "description": "Exam or final project date, time, and venue."
                    },
                    "CombinedClassInformation": {
                        "type": "string",
                        "description": "Combined class information."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_courses_by_module",
            "description": "Allows the student to query the courses contained in a module based on a module query (supports fuzzy matching).",
            "parameters": {
                "type": "object",
                "properties": {
                    "module_query": {
                        "type": "string",
                        "description": "The module query information, which can be a module number or partial module name."
                    }
                },
                "required": ["module_query"]
            }
        }
    },
    {   "type": "function",
        "function": {
            "name": "check_time_conflict_for_new_selection",
            "description": "Detect whether there is a time conflict between the newly selected course and the already selected course。Read all the courses the student has chosen from the database, then compare them with the newly chosen course times, and return a prompt if there is a conflict.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string", "description": "The student's ID."},
                    "new_course_id": {"type": "string", "description": "The new course ID, which need to check."},
                    "new_class_letter": {"type": "string", "description": "The new class letter (A, B, C, or D)."},
                },
                "required": ["new_course_id", "new_class_letter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_courses_mutual_conflict",
            "description": "Detect whether there is time conflict among multiple courses。If the user queries (or selects) multiple courses at one time, obtain the CombinedClassInformation of each course from the database, and then check whether the CombinedClassInformation of each course conflicts with each other after parsing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_list": {
                        "type": "array",
                        "description": "An array of [course_id, class_letter] to be checked for mutual time conflicts",
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                        },
                    },
                },
                "required": ["course_list"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_option_conflict",
            "description": "Obtain the courses chosen by students from the database and compare them with the custom conflict_map to determine elective conflicts. For example, some courses may be mutually exclusive",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "string",
                        "description": "The student's ID."
                    },
                    "new_course_id": {
                        "type": "string",
                        "description": "The new course ID to be checked for mutual exclusion."
                    },
                },
                "required": ["new_course_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_courses_based_on_scenario",
            "description": "Recommend courses based on scenarios like high GPA or internships. If users want to get course recommendations based on specific scenarios, such as 'high_gpa', 'career_path', or 'internship', use this function and give them some suggestions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario": {"type": "string", "description": "The recommendation scenario, e.g., 'high_gpa', 'career_path', 'internship'."},
                    "subtype": {"type": "string", "description": "Specific subtype for career_path, e.g., 'data_scientist_internet'."}
                },
                "required": ["scenario"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name":"get_program_introduction",
            "description": "Provides an overview or details about the academic structure, capstone, and other features of the program.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The specific topic to fetch, e.g., 'academic_structure' or 'capstone'."}
                },
                "required": [],
            },
        },
    }, 
      {
  "type": "function",
  "function": {
    "name": "get_stream_courses",
    "description": "Retrieves the course groups for a specified stream (e.g., 'ai', 'mc'), then returns a user-friendly string listing all courses.",
    "parameters": {
      "type": "object",
      "properties": {
        "stream": {
          "type": "string",
          "description": "The name/code of the stream, such as 'ai' or 'mc'."
        }
      },
      "required": [
        "stream"
      ]
    }
  }
}
        
    ]


    # 可用函数映射
    def get_available_functions(student_id):
        return {
            "select_course": lambda **kwargs: select_course(cursor, conn, student_id=student_id, **kwargs),
            "drop_course": lambda **kwargs: drop_course(cursor, conn, student_id=student_id, **kwargs),
            "query_selected_courses": lambda **kwargs: query_selected_courses(cursor, student_id=student_id,**kwargs),
            "view_stream": lambda **kwargs: view_stream(cursor, student_id=student_id,**kwargs),
            "modify_stream": lambda **kwargs: modify_stream(cursor, conn, student_id=student_id, **kwargs),
            "validate_stream_requirements": lambda **kwargs: validate_stream_requirements(cursor, student_id=student_id,**kwargs),
            "join_waiting_queue": lambda **kwargs: join_waiting_queue(cursor, conn,student_id=student_id,**kwargs),
            "cancel_waiting": lambda **kwargs: cancel_waiting(cursor,conn, student_id=student_id,**kwargs),
            "query_waiting_courses": lambda **kwargs: query_waiting_courses(cursor, student_id=student_id,**kwargs),
            "count_waiting_queue": lambda **kwargs: count_waiting_queue(cursor, student_id=student_id,**kwargs),
            "advanced_course_query": lambda **kwargs: advanced_course_query(cursor, **kwargs),
            "get_courses_by_module": lambda **kwargs: get_courses_by_module(cursor, **kwargs),
            "check_time_conflict_for_new_selection": lambda **kwargs: check_time_conflict_for_new_selection(cursor, student_id=student_id, **kwargs),
            "check_courses_mutual_conflict": lambda **kwargs: check_courses_mutual_conflict(cursor, **kwargs),
            "check_option_conflict": lambda **kwargs: check_option_conflict(cursor, **kwargs),
            "recommend_courses_based_on_scenario": lambda **kwargs: recommend_courses_based_on_scenario(cursor, **kwargs),
            "get_program_introduction": lambda **kwargs: get_program_introduction(cursor, **kwargs),
            "get_stream_courses": lambda **kwargs: get_stream_courses(cursor, **kwargs)
            
        }

    # 定义助手存在检查函数
    def assistant_exists(assistant_id: str) -> bool:
        try:
            client.beta.assistants.retrieve(assistant_id=assistant_id)
            return True
        except Exception:
            return False
        
    # 检查助手和线程是否已存在
    assistant_id = "asst_Sb1W9jVTeL1iyzu6N5MilgA1"
    if 'assistant' not in st.session_state:
        if assistant_exists(assistant_id):
            st.session_state.assistant = client.beta.assistants.retrieve(assistant_id=assistant_id)
        else:
            st.session_state.assistant = client.beta.assistants.create(
                name="Course Selection Assistant",
                instructions= instruction,
                tools=tools_list,
                model=api_deployment_name,
            )
        st.session_state.thread = client.beta.threads.create()


    assistant = st.session_state.assistant
    thread = st.session_state.thread


    def call_functions(client: AzureOpenAI, thread: Thread, run: Run) -> None:
        required_actions = run.required_action.submit_tool_outputs.model_dump()
        tool_outputs = []
        import json

        for action in required_actions["tool_calls"]:
            func_name = action["function"]["name"]
            arguments = json.loads(action["function"]["arguments"])
            
            # 记录函数调用信息
            logger.info(f"Calling function: {func_name}") ##
            logger.info(f"Arguments: {arguments}") ##
            
            try:
                if func_name == "select_course":
                    output = select_course(cursor, conn, student_id=st.session_state.student_id, **arguments)
                elif func_name == "drop_course":
                    output = drop_course(cursor, conn, student_id=st.session_state.student_id, **arguments)
                elif func_name == "query_selected_courses":
                    output = query_selected_courses(cursor, student_id=st.session_state.student_id)
                elif func_name == "view_stream":
                    output = view_stream(cursor, student_id=st.session_state.student_id)
                elif func_name == "modify_stream":
                    output = modify_stream(cursor, conn, student_id=st.session_state.student_id, **arguments)
                elif func_name == "validate_stream_requirements":
                    output = validate_stream_requirements(cursor, student_id=st.session_state.student_id)
                elif func_name == "join_waiting_queue": 
                    output = join_waiting_queue(cursor, conn, student_id=st.session_state.student_id, **arguments)
                elif func_name == "cancel_waiting":
                    output = cancel_waiting(cursor, conn, student_id=st.session_state.student_id, **arguments)
                elif func_name == "query_waiting_courses":
                    output = query_waiting_courses(cursor, student_id=st.session_state.student_id, **arguments)
                elif func_name == "count_waiting_queue":
                    output = count_waiting_queue(cursor, student_id=st.session_state.student_id, **arguments)
                elif func_name == "advanced_course_query":
                    output = advanced_course_query(cursor, **arguments)
                elif func_name == "get_courses_by_module":
                    output = get_courses_by_module(cursor, **arguments)
                elif func_name == "check_time_conflict_for_new_selection":
                    output = check_time_conflict_for_new_selection(cursor, student_id=st.session_state.student_id, **arguments)
                elif func_name == "check_courses_mutual_conflict":
                    output = check_courses_mutual_conflict(cursor, **arguments)
                elif func_name == "check_option_conflict":
                    output = check_option_conflict(cursor, **arguments)
                elif func_name == "recommend_courses_based_on_scenario":
                    output = recommend_courses_based_on_scenario(cursor, scenario=arguments["scenario"])
                elif func_name == "get_program_introduction":
                    output = get_program_introduction(cursor, **arguments)
                elif func_name == "get_stream_courses":
                    output = get_stream_courses(cursor, **arguments)
                else:
                    output = f"Unknown function: {func_name}"
                # 记录函数返回值
                logger.info(f"Function {func_name} output: {output}") ## 记录函数返回值
                # 将输出添加到 tool_outputs
                tool_outputs.append({"tool_call_id": action["id"], "output": json.dumps(output)})

            except Exception as e:
                # 捕获异常，将错误信息返回给助手
                error_msg = f"Error in {func_name}: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg) ## 记录错误信息
                tool_outputs.append({"tool_call_id": action["id"], "output": json.dumps(error_msg)})

        client.beta.threads.runs.submit_tool_outputs(thread_id=thread.id, run_id=run.id, tool_outputs=tool_outputs)

    if 'available_functions' not in st.session_state:
        st.session_state.available_functions = get_available_functions(st.session_state.student_id)

    # Function to format and display the Assistant Messages for text and images
    def format_messages(messages: Iterable[Message]) -> None:
        # print(messages)
        message_list = []

        for message in messages:
            message_list.append(message)
            if message.role == "user":
                break

        message_list.reverse()

        response_list = []
        for message in message_list:
            for item in message.content:
                if isinstance(item, TextContentBlock):
                    response_list.append(item.text.value)
        return response_list
                    
    def process_message(content: str) -> None:
        try:
            client.beta.threads.messages.create(thread_id=thread.id, role="user", content=content,)
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id,
                instructions="The current date and time is: " + datetime.now().strftime("%x %X") + ".",
            )

            while True:
                run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
                if run.status == "completed":
                    messages = client.beta.threads.messages.list(thread_id=thread.id)
                    return format_messages(messages)
                    break
                elif run.status == "failed":
                    messages = client.beta.threads.messages.list(thread_id=thread.id)
                    return format_messages(messages)
                    st.error("Processing failed. Please try again.")
                    break
                elif run.status == "expired":
                    st.error("Session expired. Please try again.")
                    break
                elif run.status == "cancelled":
                    st.error("Processing was cancelled. Please try again.")
                    break
                elif run.status == "requires_action":
                    call_functions(client, thread, run)
                else:
                    time.sleep(5)
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            st.info("Please try your question again.")

    ##########################
    # 侧边栏
    with st.sidebar:
        st.write('Empty history and start a new chat')
        if st.button("\+ New Chat"):
            response = """Hello! I am a smart assistant supporting you the following tasks:\n
                Introduce our program
    Answer course information
    select or drop courses
    View or change the stream(AI/MC)
    Check course requirements
    Recommend courses based on your need
    ..."""
            st.session_state.messages = [{"role": "assistant", "content": response}]
        st.divider()
        st.write('Click to log out')
        if st.button("Log Out"):
            del st.session_state.logged_in
            del st.session_state.student_id
            del st.session_state.messages
            del st.session_state.assistant
            del st.session_state.thread
            del st.session_state.available_functions
            st.rerun()
        st.divider()

    st.image("head.png", use_container_width=True)
    st.divider()
    st.write("## 🚀 Course Registration Assistant")
    
    # 在主界面中添加日志显示区域
    if st.sidebar.checkbox("Show Debug Logs"):
        with st.expander("Function Call Logs"):
            if os.path.exists('agent_logs.txt'):
                with open('agent_logs.txt', 'r') as f:
                    logs = f.read()
                    st.text_area("Logs", logs, height=300)

    # Initialize chat history
    if "messages" not in st.session_state:
        response = """Hello! I am a smart assistant supporting you the following tasks:\n
            Introduce our program
    Answer course information
    Select or drop courses
    View or change the stream(AI/MC)
    Check course requirements
    Recommend courses based on your need
    ..."""
        st.session_state.messages = [{"role": "assistant", "content": response}]

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("Send a message"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            response_list = process_message(prompt)
            if response_list:
                response = response_list[1]
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            else:
                response = st.markdown("Something went wrong. Please try again.")
                st.session_state.messages.append({"role": "assistant", "content": response})
    ##########################
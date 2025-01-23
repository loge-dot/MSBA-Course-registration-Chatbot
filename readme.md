# **CourseMate: LLM-Powered Registration Assistant**

This project is a **CourseMate: LLM-Powered Registration Assistant** that enables students to interact with a virtual assistant for selecting courses, managing streams, and tracking enrollment status. The system also features AI-based course recommendations and queue management for fully booked classes.

This project was developed by **Group 5**, with the original concept created by **Professor Hailiang**. Six students from Group 5 collaborated to bring this idea to life.

---

## **Purpose**

The main objective of this project is to create a **Course Registration Chatbot** that automates the process of course selection. Students no longer need to repeatedly check course details or schedules manually. Instead, they can interact with the chatbot to retrieve information, register for courses, and even receive personalized course recommendations.

---

## **Key Features**

- **Course Selection and Drop:** Select and drop courses easily.
- **Stream Management:** Choose between academic streams (AI/MC) and check associated requirements.
- **Queue Management:** Automatically queue for full courses and monitor your status.
- **Course Conflict Detection:** Detect conflicts in course timings or content.
- **Recommendations:** Get course suggestions based on specific scenarios.

---

## **File Structure and Descriptions**

### **Main Files**

- **`chatbot.py`**: This Python file is the core of the chatbot. It runs the UI for all functionalities, stores the design of the user interface, manages the debugging process, and lists all prompts and tools.
- **`functions.py`**: Contains all the functions that power the chatbot. It provides the necessary functionality for course selection, stream management, queue management, etc.
- **`test.file`** : For evaluation and testing, we created a comprehensive question flow, involving 100 students and 15 distinct questions.

### **Data Files**

- **`merged_data.csv`**: Contains all real-world course details.
  - **`Course_class.csv`**: Links courses with the corresponding classes.
  - **`Module_course.csv`**: Links courses with their associated modules.
  - **`stream_data.csv`**: Associates courses with specific streams.
- **`recommendations.json`**: Stores course recommendations based on different student scenarios (e.g., academic progress, career goals).
- **`program_info.json`**: Contains basic information about the academic programs and courses offered.

### **SQL Database**

- **`course_selection.db`**: Stores information about every course selected by each student.
- **`course.db`**: Stores detailed course information, converted from the `merged_data.csv` file.

### **Temporary SQL Database**

- **`students`**: Stores student account details and passwords.
- **`classes`**: Tracks the number of students enrolled in each class.
- **`stream_requirements`**: Stores data related to stream requirements (e.g., prerequisites or special conditions).
- **`waiting_queue`**: Stores information about students on the waiting list for fully-booked courses.

### **Other Files**

- **`agent_logs.txt`**: Logs all chatbot interactions and debug responses for system diagnostics and troubleshooting.
- **`bg.png`**: Background image for the chatbot interface.
- **`head.png`**: Profile image used in the chatbot UI.

---

## **How to use it**

1. run `chatbot.py` and input `python -m streamlit run chatbot.py` in the terminal.
2. Login accounts: students1, Password: password1
3. Please test the add-to-queue function after logging in using other three student id to select same course, since we assume the class capacity is 3 for easy test.


## **Attention**

1. If informed 'the class does not exist' during course selection, please open the terminal again and run the program
2. Please enter the prompt clearly: enter the course id and class letter when select course, enter 'check the conflicts' when test course conflict function to avoid unnecessary errors.
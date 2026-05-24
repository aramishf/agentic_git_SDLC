<div align="center">

# ⭐ Silent Voice Bridge
### Real-Time ASL-to-English Translator

<br/>

Silent Voice Bridge is an accessibility tool designed to bridge the communication gap for the Deaf and Hard of Hearing community. It uses computer vision to translate American Sign Language (ASL) fingerspelling into English text in real-time.

</div>

---

# Project Demonstration

Watch as the system translates real-time ASL fingerspelling into text:

<div align="center">

![Aramish signing "my name is aramish"](demo.mov)

*Live translation using 3D hand landmarks and custom LSTM model.*
</div>

---

# Key Features & Tech Stack

### 🚀 Key Features
* **Architecture:** Engineered a low-latency WebSocket pipeline connecting a React frontend to a high-performance Python FastAPI backend.
* **Computer Vision:** Integrated MediaPipe Hands to extract 21 3D landmarks in real-time for precise fingerspelling detection.
* **LSTM Engine:** Trained a custom LSTM model on self-collected datasets (A-Z, 0-9) of normalized landmark arrays for robust real-world inference.

### 💻 Tech Stack
* **Frontend:** React, WebSockets
* **Backend:** Python, FastAPI
* **Machine Learning:** MediaPipe, LSTM (Long Short-Term Memory Networks)

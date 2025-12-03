document.addEventListener("DOMContentLoaded", async () => {
    let ttsEnabled = true;  // default ON

    // TTS toggle
    const ttsToggle = document.getElementById("tts-toggle");
    if (ttsToggle) {
        ttsToggle.checked = ttsEnabled;
        ttsToggle.addEventListener("change", (e) => {
            ttsEnabled = e.target.checked;
        });
    }

    // ============================
    // INTRO PARAGRAPH READ-ALOUD
    // ============================
    const introBtn = document.getElementById("read-intro-btn");
    if (introBtn) {
        introBtn.addEventListener("click", () => {
            if (!ttsEnabled) return;
            const introTextEl = document.getElementById("intro-text");
            if (introTextEl) speakText(introTextEl.textContent);
        });
    }

    // ============================
    // QUIZ VARIABLES
    // ============================
    const questionBox = document.getElementById("question-box");
    const progressBar = document.getElementById("progress-bar");
    const progressText = document.getElementById("progress-text");
    const quizTitle = document.getElementById("quiz-title");
    const language = window.location.pathname.split("/").pop();

    // ============================
    // LOAD QUESTION
    // ============================
    async function loadQuestion() {
        const response = await fetch(`/quiz/${language}/get_question`);
        const data = await response.json();

        const total = data.total_questions ?? 0;
        const qNum = data.question_number ?? 0;

        if (data.finished) {
            questionBox.innerHTML = `
                <h2>🎉 Quiz Finished!</h2>
                <p class="score">Your score: ${data.score} / ${total}</p>
                <div style="text-align:center; margin-top:30px;">
                    <button id="restart-btn">Restart Quiz</button>
                    <a href="/"><button>Back to Home</button></a>
                </div>
            `;
            progressBar.style.width = "100%";
            progressText.textContent = `Progress: ${total} / ${total}`;
            document.getElementById("restart-btn").addEventListener("click", () => {
                window.location.href = `/quiz/${language}?reset=1`;
            });
            return;
        }

        quizTitle.textContent = `Quiz: ${data.language.charAt(0).toUpperCase() + data.language.slice(1)}`;
        progressBar.style.width = `${(qNum / total) * 100}%`;
        progressText.textContent = `Progress: ${qNum} / ${total}`;

        let optionsHtml = "";
        data.options.forEach(opt => {
            optionsHtml += `
                <div class="option">
                    <input type="radio" name="option" value="${opt}" required> ${opt}
                </div>
            `;
        });

        questionBox.innerHTML = `
            <p id="quiz-question"><strong>${data.question}</strong></p>
            <form id="quiz-form">
                ${optionsHtml}
                <button type="submit">Submit Answer</button>
            </form>
            <div id="feedback"></div>
        `;

        // Speak question aloud if enabled
        if (ttsEnabled) speakText(data.question);

        document.getElementById("quiz-form").addEventListener("submit", submitAnswer);
    }

    // ============================
    // SUBMIT ANSWER
    // ============================
    async function submitAnswer(event) {
        event.preventDefault();
        const form = event.target;
        const selected = form.option.value;

        const response = await fetch(`/quiz/${language}/answer`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({selected})
        });

        const data = await response.json();

        const total = data.total_questions ?? 0;
        const qNum = data.question_number ?? 0;

        document.getElementById("feedback").innerHTML = `
            <p><strong>${data.feedback_msg}</strong></p>
            <p><em>${data.explanation}</em></p>
        `;

        // Speak explanation if enabled
        if (ttsEnabled) speakText(`${data.feedback_msg}. ${data.explanation}`);

        const options = document.querySelectorAll(".option");
        options.forEach(optDiv => {
            const text = optDiv.textContent.trim();
            if (text === data.correct) optDiv.classList.add("correct");
            else if (text === selected) optDiv.classList.add("incorrect");
        });

        progressBar.style.width = `${(qNum / total) * 100}%`;
        progressText.textContent = `Progress: ${qNum} / ${total}`;

        setTimeout(loadQuestion, 1500);
    }

    // ============================
    // SPEECH FUNCTION
    // ============================
    function speakText(text) {
        if (!text || !ttsEnabled) return;
        const msg = new SpeechSynthesisUtterance(text);
        msg.rate = 1;
        msg.pitch = 1;
        msg.lang = 'en-US';
        window.speechSynthesis.speak(msg);
    }

    // ============================
    // INITIALIZE
    // ============================
    loadQuestion();
});
document.addEventListener("DOMContentLoaded", async () => {
    const questionBox = document.getElementById("question-box");
    const progressBar = document.getElementById("progress-bar");
    const progressText = document.getElementById("progress-text");
    const quizTitle = document.getElementById("quiz-title");

    const language = window.location.pathname.split("/").pop();

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
            <p><strong>${data.question}</strong></p>
            <form id="quiz-form">
                ${optionsHtml}
                <button type="submit">Submit Answer</button>
            </form>
            <div id="feedback"></div>
        `;

        document.getElementById("quiz-form").addEventListener("submit", submitAnswer);
    }

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

    loadQuestion();
});
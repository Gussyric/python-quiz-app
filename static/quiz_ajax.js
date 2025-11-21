document.addEventListener("DOMContentLoaded", async () => {
    const questionBox = document.getElementById("question-box");
    const progressBar = document.getElementById("progress-bar");
    const progressText = document.getElementById("progress-text");
    const quizTitle = document.getElementById("quiz-title");

    const language = window.location.pathname.split("/").pop();

    // Fetch and display the current question
    async function loadQuestion() {
        const response = await fetch(`/quiz/${language}`);
        const data = await response.json();

        if (data.finished) {
            questionBox.innerHTML = `
                <h2>Quiz Finished!</h2>
                <p class="score">Your score: ${data.score} / ${data.total}</p>
                <div style="text-align:center; margin-top:30px;">
                    <a href="/"><button>Back to Home</button></a>
                </div>
            `;
            progressBar.style.width = "100%";
            progressText.textContent = `Progress: ${data.total} / ${data.total}`;
            return;
        }

        quizTitle.textContent = `Quiz: ${data.language.charAt(0).toUpperCase() + data.language.slice(1)}`;
        progressBar.style.width = `${(data.question_number / data.total_questions) * 100}%`;
        progressText.textContent = `Progress: ${data.question_number} / ${data.total_questions}`;

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

        // Attach submit listener
        document.getElementById("quiz-form").addEventListener("submit", submitAnswer);
    }

    // Submit answer to server
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

        // Show feedback and AI explanation
        let feedbackHtml = `
            <p><strong>${data.feedback_msg}</strong></p>
            <p><em>${data.explanation}</em></p>
        `;

        questionBox.innerHTML += feedbackHtml;

        // Highlight options
        const options = questionBox.querySelectorAll(".option");
        options.forEach(optDiv => {
            const text = optDiv.textContent.trim();
            if (text === data.correct) {
                optDiv.classList.add("correct");
            } else if (text === selected) {
                optDiv.classList.add("incorrect");
            }
        });

        // Show next question after 1.5s
        setTimeout(loadQuestion, 1500);
    }

    // Initial load
    loadQuestion();
});
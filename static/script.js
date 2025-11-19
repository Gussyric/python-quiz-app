document.addEventListener("DOMContentLoaded", () => {
    const questionBox = document.getElementById("question-box");
    if (questionBox) {
        questionBox.classList.add("fade-in");
    }

    const quizForm = document.getElementById("quiz-form");
    if (quizForm) {
        quizForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const formData = new FormData(quizForm);
            const selected = formData.get("option");
            const language = window.location.pathname.split("/").pop();

            // Send POST request via fetch
            const response = await fetch(`/quiz/${language}`, {
                method: "POST",
                body: formData
            });

            const html = await response.text();

            // Replace the quiz container with the new HTML
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");
            const newQuestionBox = doc.getElementById("question-box");
            if (newQuestionBox) {
                questionBox.innerHTML = newQuestionBox.innerHTML;

                // Highlight correct/incorrect options
                const feedbackMsg = doc.getElementById("feedback-msg")?.textContent || "";
                const options = document.querySelectorAll(".option");
                options.forEach(opt => {
                    const text = opt.textContent.trim();
                    if (text.includes(feedbackMsg)) {
                        opt.classList.add("correct");
                    }
                    if (text.includes(selected) && !text.includes(feedbackMsg)) {
                        opt.classList.add("incorrect");
                    }
                });
            }
        });
    }
});
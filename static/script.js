// Add fade animation to question section
document.addEventListener("DOMContentLoaded", () => {
    let questionBox = document.getElementById("question-box");
    if (questionBox) {
        questionBox.classList.add("fade-in");
    }
});

// Auto highlight correct / incorrect options after submit
function highlightAnswer(selected, correct) {
    let options = document.querySelectorAll(".option");

    options.forEach(opt => {
        let text = opt.textContent.trim();

        if (text === correct) {
            opt.classList.add("correct");
        } 
        if (text === selected && selected !== correct) {
            opt.classList.add("incorrect");
        }
    });
}
let timeLeft = 25 * 60;
let selectedMinutes = 25;
let timerInterval = null;

function updateTimer() {
    const timer = document.getElementById("timer");

    if (!timer) return;

    const minutes = Math.floor(timeLeft / 60);
    const seconds = timeLeft % 60;

    timer.textContent =
        String(minutes).padStart(2, "0") + ":" +
        String(seconds).padStart(2, "0");
}

function setTimer(minutes) {
    pauseTimer();

    selectedMinutes = minutes;
    timeLeft = minutes * 60;

    document.querySelectorAll(".preset").forEach(btn => {
        btn.classList.remove("active");

        if (btn.textContent.includes(minutes + " min")) {
            btn.classList.add("active");
        }
    });

    updateTimer();
}

function setCustomTimer() {
    const input = document.getElementById("customMinutes");

    if (!input) return;

    const minutes = Number(input.value);

    if (!minutes || minutes < 1 || minutes > 240) {
        alert("Enter a value between 1 and 240 minutes.");
        return;
    }

    setTimer(minutes);
}

function startTimer() {
    if (timerInterval !== null) return;

    timerInterval = setInterval(() => {

        if (timeLeft > 0) {
            timeLeft--;
            updateTimer();
        } else {
            clearInterval(timerInterval);
            timerInterval = null;

            alert("🎉 Study session complete!");
        }

    }, 1000);
}

function pauseTimer() {
    if (timerInterval !== null) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function resetTimer() {
    pauseTimer();
    timeLeft = selectedMinutes * 60;
    updateTimer();
}

updateTimer();

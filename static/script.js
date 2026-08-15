const TIMER_STORAGE_KEY = "studyTimerState";

let timeLeft = 25 * 60;
let selectedMinutes = 25;
let timerInterval = null;
let endTime = null;
let isRunning = false;


/* =========================================
   SAVE TIMER STATE
========================================= */

function saveTimerState() {
    const state = {
        selectedMinutes: selectedMinutes,
        timeLeft: timeLeft,
        endTime: endTime,
        isRunning: isRunning
    };

    localStorage.setItem(
        TIMER_STORAGE_KEY,
        JSON.stringify(state)
    );
}


/* =========================================
   LOAD TIMER STATE
========================================= */

function loadTimerState() {

    const saved = localStorage.getItem(TIMER_STORAGE_KEY);

    if (!saved) {
        updateTimer();
        return;
    }

    try {

        const state = JSON.parse(saved);

        selectedMinutes =
            Number(state.selectedMinutes) || 25;

        timeLeft =
            Number(state.timeLeft) ||
            selectedMinutes * 60;

        endTime = state.endTime || null;

        isRunning = state.isRunning === true;


        /*
         * If the timer was running while
         * the user was away, calculate the
         * actual remaining time.
         */

        if (isRunning && endTime) {

            timeLeft = Math.max(
                0,
                Math.ceil(
                    (endTime - Date.now()) / 1000
                )
            );

            if (timeLeft <= 0) {
                finishTimer();
                return;
            }
        }

        updateTimer();

        if (isRunning) {
            startInterval();
        }

    } catch (error) {

        console.error(
            "Could not restore timer:",
            error
        );

        localStorage.removeItem(
            TIMER_STORAGE_KEY
        );

        timeLeft = 25 * 60;
        selectedMinutes = 25;
        endTime = null;
        isRunning = false;

        updateTimer();
    }
}


/* =========================================
   UPDATE TIMER DISPLAY
========================================= */

function updateTimer() {

    const timer =
        document.getElementById("timer");

    /*
     * The script runs on all pages.
     * Only update the display when the
     * Timer page actually contains #timer.
     */

    if (!timer) return;

    const minutes =
        Math.floor(timeLeft / 60);

    const seconds =
        timeLeft % 60;

    timer.textContent =
        String(minutes).padStart(2, "0") +
        ":" +
        String(seconds).padStart(2, "0");
}


/* =========================================
   SET PRESET TIMER
========================================= */

function setTimer(minutes) {

    pauseTimer();

    selectedMinutes = minutes;
    timeLeft = minutes * 60;

    endTime = null;
    isRunning = false;

    localStorage.removeItem(
        TIMER_STORAGE_KEY
    );


    /*
     * Update active preset button.
     */

    document
        .querySelectorAll(".preset")
        .forEach(btn => {

            btn.classList.remove("active");

            if (
                btn.textContent.includes(
                    minutes + " min"
                )
            ) {
                btn.classList.add("active");
            }
        });

    updateTimer();
}


/* =========================================
   SET CUSTOM TIMER
========================================= */

function setCustomTimer() {

    const input =
        document.getElementById(
            "customMinutes"
        );

    if (!input) return;

    const minutes =
        Number(input.value);

    if (
        !minutes ||
        minutes < 1 ||
        minutes > 240
    ) {

        alert(
            "Enter a value between 1 and 240 minutes."
        );

        return;
    }

    setTimer(minutes);
}


/* =========================================
   START TIMER
========================================= */

function startTimer() {

    if (isRunning) return;

    /*
     * If timer reached zero, restart
     * from the selected duration.
     */

    if (timeLeft <= 0) {
        timeLeft =
            selectedMinutes * 60;
    }

    /*
     * Store the exact time when the
     * timer should finish.
     */

    endTime =
        Date.now() +
        (timeLeft * 1000);

    isRunning = true;

    saveTimerState();

    startInterval();
}


/* =========================================
   START COUNTDOWN INTERVAL
========================================= */

function startInterval() {

    /*
     * Prevent multiple intervals.
     */

    if (timerInterval !== null) return;

    /*
     * 250 ms makes the display more
     * responsive, while the actual
     * time is calculated from Date.now().
     */

    timerInterval = setInterval(() => {

        if (
            !isRunning ||
            !endTime
        ) {
            return;
        }

        /*
         * Calculate remaining time from
         * the real clock instead of simply
         * subtracting one every second.
         */

        timeLeft = Math.max(
            0,
            Math.ceil(
                (endTime - Date.now()) /
                1000
            )
        );

        updateTimer();

        /*
         * Keep the latest state saved.
         */

        saveTimerState();

        if (timeLeft <= 0) {
            finishTimer();
        }

    }, 250);
}


/* =========================================
   PAUSE TIMER
========================================= */

function pauseTimer() {

    if (!isRunning) return;

    /*
     * Calculate the exact remaining time
     * before pausing.
     */

    if (endTime) {

        timeLeft = Math.max(
            0,
            Math.ceil(
                (endTime - Date.now()) /
                1000
            )
        );
    }

    isRunning = false;
    endTime = null;

    if (timerInterval !== null) {

        clearInterval(timerInterval);

        timerInterval = null;
    }

    saveTimerState();

    updateTimer();
}


/* =========================================
   RESET TIMER
========================================= */

function resetTimer() {

    pauseTimer();

    timeLeft =
        selectedMinutes * 60;

    endTime = null;
    isRunning = false;

    localStorage.removeItem(
        TIMER_STORAGE_KEY
    );

    updateTimer();
}


/* =========================================
   TIMER FINISHED
========================================= */

function finishTimer() {

    timeLeft = 0;

    endTime = null;
    isRunning = false;

    if (timerInterval !== null) {

        clearInterval(timerInterval);

        timerInterval = null;
    }

    /*
     * Remove completed timer state.
     */

    localStorage.removeItem(
        TIMER_STORAGE_KEY
    );

    updateTimer();

    alert(
        "🎉 Study session complete!"
    );
}


/* =========================================
   RESTORE TIMER WHEN ANY PAGE LOADS
========================================= */

loadTimerState();
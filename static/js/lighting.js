document.addEventListener("DOMContentLoaded", function () {

    const room = document.querySelector(".lighting-room");
    const buttons = document.querySelectorAll(".time-option");
    const timeDisplay = document.querySelector(".lighting-time");
    const heading = document.querySelector(".lighting-controls h3");

    if (!room || buttons.length === 0) {
        return;
    }

    const lightingModes = {

        morning: {
            className: "lighting-morning",
            time: "08:00 AM",
            title: "Fresh morning light"
        },

        evening: {
            className: "lighting-evening",
            time: "06:00 PM",
            title: "Evening ambience"
        },

        night: {
            className: "lighting-night",
            time: "10:00 PM",
            title: "Warm night lighting"
        }

    };


    buttons.forEach(function (button) {

        button.addEventListener("click", function () {

            const selectedTime = button.dataset.time;

            const mode = lightingModes[selectedTime];

            if (!mode) {
                return;
            }


            /* Remove previous lighting modes */

            room.classList.remove(
                "lighting-morning",
                "lighting-evening",
                "lighting-night"
            );


            /* Apply selected lighting */

            room.classList.add(mode.className);


            /* Update active button */

            buttons.forEach(function (btn) {
                btn.classList.remove("active");
            });

            button.classList.add("active");


            /* Update time */

            if (timeDisplay) {
                timeDisplay.textContent = mode.time;
            }


            /* Update heading */

            if (heading) {
                heading.textContent = mode.title;
            }

        });

    });

});
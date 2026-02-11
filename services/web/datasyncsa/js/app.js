/**
 * Datasyncsa Interactive Effects
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('Datasyncsa: Initializing effects...');

    const part1 = document.getElementById('title-part-1');
    const part2 = document.getElementById('title-part-2');

    // Check if elements exist to avoid errors
    if (!part1 || !part2) {
        console.error('Datasyncsa: Title elements not found!');
        return;
    }

    const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ#%&@$0123456789";

    // Generalized scramble function
    function scrambleElement(element) {
        const originalText = element.dataset.originalText || element.innerText;
        element.dataset.originalText = originalText; // cache it

        // Prevent layout shift (vibration) by locking width
        if (!element.style.width) {
            const rect = element.getBoundingClientRect();
            element.style.display = 'inline-block';
            element.style.verticalAlign = 'top'; // Prevent vertical alignment shift
            element.style.width = `${rect.width}px`;
            // Ensure it doesn't wrap unexpectedly
            element.style.whiteSpace = 'nowrap';
        }

        let iteration = 0;
        let interval = null;

        clearInterval(element.dataset.intervalId);

        interval = setInterval(() => {
            element.innerText = originalText
                .split("")
                .map((letter, index) => {
                    if (index < iteration) {
                        return originalText[index];
                    }
                    if (letter === " ") return " ";
                    return letters[Math.floor(Math.random() * letters.length)];
                })
                .join("");

            if (iteration >= originalText.length) {
                clearInterval(interval);
                element.innerHTML = originalText; // Restore exact HTML/Text
            }

            iteration += 1 / 2; // Speed of decoding
        }, 30);

        element.dataset.intervalId = interval;
    }

    // Trigger on load
    setTimeout(() => {
        scrambleElement(part1);
        setTimeout(() => scrambleElement(part2), 500); // Staggered start
    }, 100);

    // Trigger on hover of the container
    const heroTitle = document.getElementById('hero-title');
    if (heroTitle) {
        heroTitle.addEventListener('mouseenter', () => {
            scrambleElement(part1);
            scrambleElement(part2);
        });
    }

    console.log('Datasyncsa: Effects active.');

});

(() => {

    class DOMHelper {
        static query(selector, all = false) {
            return all ? [...document.querySelectorAll(selector)] : document.querySelector(selector);
        }

        static trigger(el, events = []) {
            if (!el) return;
            for (const evt of events) {
                el.dispatchEvent(new Event(evt, { bubbles: true }));
            }
        }

        static waitForElement(selector, interval = 20) {
            return new Promise(resolve => {
                const timer = setInterval(() => {
                    const el = DOMHelper.query(selector);
                    if (el) {
                        clearInterval(timer);
                        resolve(el);
                    }
                }, interval);
            });
        }

        static waitForCondition(fn, interval = 20) {
            return new Promise(resolve => {
                const check = () => {
                    const result = fn();
                    if (result) resolve(result);
                    else setTimeout(check, interval);
                };
                check();
            });
        }
    }

    function setInput(selector, value) {
        const el = DOMHelper.query(selector);
        if (el) {
            el.value = value;
            DOMHelper.trigger(el, ['input', 'change']);
        }
    }

    function clickCheckbox(selector) {
        const el = DOMHelper.query(selector);
        if (el && el.getAttribute('aria-checked') === 'false') el.click();
    }

    function clickElement(selector) {
        const el = DOMHelper.query(selector);
        if (el) el.click();
    }

    async function setDropdown(label, value) {
        const dropdown = DOMHelper.query(`div[role="button"][aria-label="${label}"]`);
        if (!dropdown) return;

        dropdown.click();

        const options = await DOMHelper.waitForCondition(() => {
            const opts = DOMHelper.query('div[role="option"]', true);
            return opts.length > 0 ? opts : null;
        });

        const match = options.find(opt => opt.textContent.trim() === value);
        if (match) match.click();
    }

    function clickAllCheckboxes() {
        DOMHelper.query('input[type="checkbox"]', true)
            .filter(cb => !cb.checked)
            .forEach(cb => cb.click());
    }

    async function openAccessibilityChallenge() {
        const menuBtn = await DOMHelper.waitForElement('#menu-info');
        menuBtn.click();

        const accBtn = await DOMHelper.waitForCondition(() => {
            const opts = DOMHelper.query('[role="menuitem"]', true);
            return opts.find(o =>
                /Accessibility Challenge|Toegankelijkheidsuitdaging/.test(o.innerText)
            );
        });

        accBtn.click();

        await DOMHelper.waitForElement('input[name="captcha"]');

        const langBtn = DOMHelper.query('[aria-label*="Select a language"]');
        if (langBtn) {
            langBtn.click();
            const dutchOption = await DOMHelper.waitForCondition(() => {
                const langs = DOMHelper.query('[role="option"]', true);
                return langs.find(o => o.innerText.includes('Dutch'));
            });
            dutchOption.click();
        }
    }

    function answerAccessibilityQuestion(answer) {
        const input = DOMHelper.query('input[name="captcha"]');
        if (!input) return;

        input.value = answer;
        DOMHelper.trigger(input, ['input']);

        const submitButton = DOMHelper.query('.button-submit');
        if (submitButton) submitButton.click();
    }

    async function waitForDiscordToken(timeout = 5000) {
        const start = performance.now();
        while (performance.now() - start < timeout) {
            const token = localStorage.getItem('token');
            if (token) {
                return token.replace(/^"|"$/g, '');
            }
            await new Promise(r => setTimeout(r, 200));
        }
        return null;
    }

    window.utils = {
        setInput,
        clickCheckbox,
        clickElement,
        setDropdown,
        clickAllCheckboxes,
        openAccessibilityChallenge,
        answerAccessibilityQuestion,
        waitForDiscordToken
    };
})();

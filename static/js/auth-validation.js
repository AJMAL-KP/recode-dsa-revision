/**
 * ReCode - Client-side Authentication Validation
 * Submit-First Validation UX:
 * - Does NOT show premature errors on initial focus/blur
 * - Validates all fields upon form submission
 * - Preserves all entered user inputs
 * - Live-corrects errors as the user fixes them after an attempted submission
 * - Supports both Light Mode and Dark Mode styling
 */

const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
const MIN_PASSWORD_LENGTH = 8;

function validateNameValue(value) {
    const trimmed = (value || '').trim();
    if (!trimmed) {
        return { valid: false, message: 'Please enter your name.' };
    }
    return { valid: true };
}

function validateEmailValue(value) {
    const trimmed = (value || '').trim();
    if (!trimmed) {
        return { valid: false, message: 'Email address is required.' };
    }
    if (!EMAIL_REGEX.test(trimmed)) {
        return { valid: false, message: 'Please enter a valid email address (e.g. name@domain.com).' };
    }
    return { valid: true };
}

function validatePasswordValue(value, isRegistration = false) {
    if (!value) {
        return { valid: false, message: 'Password is required.' };
    }
    if (isRegistration && value.length < MIN_PASSWORD_LENGTH) {
        return { 
            valid: false, 
            message: `Password must be at least ${MIN_PASSWORD_LENGTH} characters long.` 
        };
    }
    return { valid: true };
}

function validateConfirmPasswordValue(password, confirmPassword) {
    if (!confirmPassword) {
        return { valid: false, message: 'Please confirm your password.' };
    }
    if (password !== confirmPassword) {
        return { valid: false, message: 'Passwords do not match.' };
    }
    return { valid: true };
}

function setFieldStatus(inputEl, errorEl, result) {
    if (!inputEl) return;

    if (!result.valid) {
        inputEl.classList.remove('border-slate-200', 'border-white/10', 'dark:border-white/10', 'hover:border-slate-300', 'dark:hover:border-white/20');
        inputEl.classList.add('border-orange-500', 'focus:border-orange-500');
        if (errorEl) {
            errorEl.textContent = result.message;
            errorEl.classList.remove('hidden');
        }
    } else {
        inputEl.classList.remove('border-orange-500', 'focus:border-orange-500');
        inputEl.classList.add('border-white/10');
        if (errorEl) {
            errorEl.textContent = '';
            errorEl.classList.add('hidden');
        }
    }
}

function resetFieldStatus(inputEl, errorEl) {
    if (!inputEl) return;
    inputEl.classList.remove('border-orange-500', 'focus:border-orange-500');
    inputEl.classList.add('border-white/10');
    if (errorEl) {
        errorEl.textContent = '';
        errorEl.classList.add('hidden');
    }
}

/**
 * Attach Submit-First validation to an auth form
 */
function initAuthFormValidation(formEl, options = {}) {
    if (!formEl) return;

    const isRegistration = options.isRegistration || false;
    const nameInput = formEl.querySelector('input[name="name"]');
    const emailInput = formEl.querySelector('input[name="email"]');
    const passwordInput = formEl.querySelector('input[name="password"]');
    const confirmInput = formEl.querySelector('input[name="confirm_password"]');

    const nameError = formEl.querySelector('[data-error-for="name"]');
    const emailError = formEl.querySelector('[data-error-for="email"]');
    const passwordError = formEl.querySelector('[data-error-for="password"]');
    const confirmError = formEl.querySelector('[data-error-for="confirm_password"]');

    // Only validate live AFTER the user has clicked submit once
    function shouldLiveValidate() {
        return formEl.dataset.hasSubmitted === 'true';
    }

    if (isRegistration && nameInput) {
        nameInput.addEventListener('input', () => {
            if (shouldLiveValidate()) {
                setFieldStatus(nameInput, nameError, validateNameValue(nameInput.value));
            }
        });
    }

    if (emailInput) {
        emailInput.addEventListener('input', () => {
            if (shouldLiveValidate()) {
                setFieldStatus(emailInput, emailError, validateEmailValue(emailInput.value));
            }
        });
    }

    if (passwordInput) {
        passwordInput.addEventListener('input', () => {
            if (shouldLiveValidate()) {
                setFieldStatus(passwordInput, passwordError, validatePasswordValue(passwordInput.value, isRegistration));
                if (isRegistration && confirmInput && confirmInput.value.length > 0) {
                    setFieldStatus(confirmInput, confirmError, validateConfirmPasswordValue(passwordInput.value, confirmInput.value));
                }
            }
        });
    }

    if (isRegistration && confirmInput) {
        confirmInput.addEventListener('input', () => {
            if (shouldLiveValidate()) {
                setFieldStatus(confirmInput, confirmError, validateConfirmPasswordValue(passwordInput ? passwordInput.value : '', confirmInput.value));
            }
        });
    }

    formEl.addEventListener('submit', (e) => {
        let isValid = true;
        let firstInvalidField = null;

        if (isRegistration && nameInput) {
            const nameRes = validateNameValue(nameInput.value);
            setFieldStatus(nameInput, nameError, nameRes);
            if (!nameRes.valid) {
                isValid = false;
                if (!firstInvalidField) firstInvalidField = nameInput;
            }
        }

        if (emailInput) {
            const emailRes = validateEmailValue(emailInput.value);
            setFieldStatus(emailInput, emailError, emailRes);
            if (!emailRes.valid) {
                isValid = false;
                if (!firstInvalidField) firstInvalidField = emailInput;
            }
        }

        if (passwordInput) {
            const passRes = validatePasswordValue(passwordInput.value, isRegistration);
            setFieldStatus(passwordInput, passwordError, passRes);
            if (!passRes.valid) {
                isValid = false;
                if (!firstInvalidField) firstInvalidField = passwordInput;
            }
        }

        if (isRegistration && confirmInput) {
            const confirmRes = validateConfirmPasswordValue(passwordInput ? passwordInput.value : '', confirmInput.value);
            setFieldStatus(confirmInput, confirmError, confirmRes);
            if (!confirmRes.valid) {
                isValid = false;
                if (!firstInvalidField) firstInvalidField = confirmInput;
            }
        }

        if (!isValid) {
            e.preventDefault();
            // Flag that submit was attempted so live-correction kicks in
            formEl.dataset.hasSubmitted = 'true';

            // Security: Password fields must NEVER be retained on failed submission
            if (passwordInput) {
                passwordInput.value = '';
            }
            if (confirmInput) {
                confirmInput.value = '';
            }

            // In registration, if password or confirm password was invalid, place focus on passwordInput
            if (isRegistration && (!passRes.valid || !confirmRes.valid)) {
                firstInvalidField = passwordInput;
            }

            if (firstInvalidField) {
                firstInvalidField.focus();
            }
        } else {
            // Visual feedback: prevent double submit and indicate active submission
            const submitBtn = formEl.querySelector('button[type="submit"]');
            if (submitBtn) {
                const btnText = submitBtn.querySelector('.btn-text');
                if (btnText) {
                    btnText.textContent = isRegistration ? 'Creating Account...' : 'Signing In...';
                }
                submitBtn.classList.add('opacity-75', 'cursor-wait');
                setTimeout(() => {
                    submitBtn.disabled = true;
                }, 10);
            }
        }
    });
}

// Clear password fields on initial load, reload, or back/forward navigation
function clearPasswordFields() {
    document.querySelectorAll('input[type="password"]').forEach((input) => {
        input.value = '';
    });
}

// Auto initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    clearPasswordFields();
    document.querySelectorAll('form[data-auth-type="signin"]').forEach((form) => {
        initAuthFormValidation(form, { isRegistration: false });
    });
    document.querySelectorAll('form[data-auth-type="signup"]').forEach((form) => {
        initAuthFormValidation(form, { isRegistration: true });
    });
});

window.addEventListener('pageshow', clearPasswordFields);

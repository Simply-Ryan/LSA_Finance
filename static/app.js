// =====================
// GLOBAL VARIABLES
// =====================
let debounceTimeout;

const symbolInput = document.getElementById("symbol");
const amountInput = document.getElementById("amount");

// =====================
// STOCK PRICE FETCHER
// =====================
if (symbolInput) {
    symbolInput.addEventListener("input", function () {
        clearTimeout(debounceTimeout);
        const symbol = this.value.toUpperCase();
        this.value = symbol;

        if (symbol) {
            debounceTimeout = setTimeout(() => fetchStockPrice(symbol), 500);
        }
    });
}

function fetchStockPrice(symbol) {
    const apiKey = "cu05qhpr01ql96gpu91gcu05qhpr01ql96gpu920";
    const url = `https://finnhub.io/api/v1/quote?symbol=${symbol}&token=${apiKey}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.c) {
                const stockPrice = data.c;
                const userBalance = window.userBalance || 0;
                const maxShares = Math.floor(userBalance / stockPrice);

                if (amountInput && (!amountInput.value || amountInput.value == 0)) {
                    amountInput.value = maxShares;
                }
            } else if (amountInput) {
                amountInput.value = "";
            }
        })
        .catch(error => {
            console.error("Error fetching stock price:", error);
            if (amountInput) amountInput.value = "";
        });
}

// =====================
// PASSWORD TOGGLE
// =====================
const toggleFields = [
    { fieldId: 'password', btnId: 'togglePassword' },
    { fieldId: 'confirmation', btnId: 'toggleConfirmation' }
];

toggleFields.forEach(({ fieldId, btnId }) => {
    const btn = document.getElementById(btnId);
    if (btn) {
        btn.addEventListener('click', function () {
            const input = document.getElementById(fieldId);
            const icon = this.querySelector('i');
            const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
            input.setAttribute('type', type);
            icon.classList.toggle('fa-eye');
            icon.classList.toggle('fa-eye-slash');
        });
    }
});

// =====================
// SHARES SELECTOR (SELL PAGE)
// =====================
function updateShares() {
    const symbolSelect = document.getElementById("symbol");
    if (!symbolSelect) return;

    const selectedOption = symbolSelect.options[symbolSelect.selectedIndex];
    const amount = selectedOption.getAttribute("data-amount");
    if (amountInput) amountInput.value = amount;
}

// =====================
// THEME HANDLER
// =====================
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        document.body.classList.remove('light-mode');
    } else {
        document.body.classList.add('light-mode');
        document.body.classList.remove('dark-mode');
    }

    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
        function updateButtonText() {
            toggleBtn.textContent = document.body.classList.contains('dark-mode') ?
                "Switch to Light Mode" : "Switch to Dark Mode";
        }

        updateButtonText();

        toggleBtn.addEventListener('click', function () {
            document.body.classList.toggle('light-mode');
            document.body.classList.toggle('dark-mode');
            localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
            updateButtonText();
        });
    }
}

// =====================
// FRIENDLY DATE FORMATTING
// =====================
function formatFriendlyDates() {
    document.querySelectorAll('.friendly-date').forEach(td => {
        const rawDate = td.textContent.trim();
        if (!rawDate) return;

        const dateObj = new Date(rawDate);
        if (isNaN(dateObj)) return;

        const day = dateObj.getDate();
        const month = dateObj.toLocaleString('default', { month: 'long' });
        const year = dateObj.getFullYear();
        const hours = String(dateObj.getHours()).padStart(2, '0');
        const minutes = String(dateObj.getMinutes()).padStart(2, '0');

        td.textContent = `${day} ${month} ${year} ${hours}:${minutes}`;
    });
}

// =====================
// FRIEND REMOVE MODAL
// =====================
document.addEventListener('DOMContentLoaded', function () {
    const removeModal = document.getElementById('confirmRemoveModal');
    if (removeModal) {
        removeModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const username = button.getAttribute('data-username');

            const friendName = removeModal.querySelector('#friendName');
            const friendUsernameInput = removeModal.querySelector('#friendUsername');

            friendName.textContent = username;
            friendUsernameInput.value = username;
        });
    }
});

// =====================
// DOCUMENT READY
// =====================
document.addEventListener("DOMContentLoaded", function () {
    initializeTheme();
    formatFriendlyDates();
});
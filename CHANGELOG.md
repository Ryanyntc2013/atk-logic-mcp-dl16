# Changelog

## Unreleased

### Breaking

- `logic_self_test` no longer accepts `confirm_safe_wiring` (bool). Pass `safety_confirmation="CONFIRMED_SAFE_WIRING_GUI_CLOSED"` after checking PWM0→CH8, PWM1→CH14, a safe voltage, and a closed ATK-Logic GUI. `logic_pwm` still uses `confirm_safe_wiring`.

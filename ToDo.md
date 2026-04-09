# ToDo

## Task 1: MIT Code Convention Audit & Remove Unused `move_speed`

**Date**: 2025-04-09
**GitHub Issue**: #1

### Checklist

- [x] Audit `LinearMotorController.py` against MIT Code Convention
  - [x] Docstrings: imperative mood, no signature restatement
  - [x] Naming: snake_case, descriptive verbs for methods
  - [x] Structure: 80-column limit, spacing, alignment
  - [x] Comments: complete sentences, no restating code
- [x] Confirm `move_speed` is unused by other class methods and `main()`
- [x] Remove `move_speed` from `LinearMotorController.py`
- [x] Remove `move_speed` references from `README.md`

---

## Task 2: Add mm-based Movement API & Install Cable Carrier

**Date**: 2025-04-09
**GitHub Issue**: #2

### Checklist

- [ ] Measure rail and determine `PULSES_PER_MM` conversion constant
- [ ] Add `move_mm(distance_mm, speed, tolerance_mm, timeout)` method
- [ ] Update `README.md` with mm-based API documentation
- [ ] Install cable carrier (케이블캐리어) for cable protection
- [ ] Create GitHub issue
- [ ] Commit and push

---

## Task 3: Fix Remaining MIT Convention Violations

**Date**: 2025-04-09
**GitHub Issue**: #3

### Checklist

- [x] Add module-level docstring
- [x] Remove empty parentheses from class declaration
- [x] Remove redundant comment (`# Mapping mode and command`)
- [x] Extract magic numbers in `main()` to named constants
- [x] Verify motor runs correctly
- [x] Commit and push

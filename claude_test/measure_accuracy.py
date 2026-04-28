"""Single-shot accuracy measurement for the CSV record.

Performs one trial per run:
  1. Returns to origin (0 mm) via the closed-loop move_to_mm to get
     a clean, repeatable starting point.
  2. Waits for residual vibration to settle (per CSV step 5).
  3. Issues one single-speed forward move via move_relative_mm.
  4. Prints the final encoder position so the operator can record
     it after measuring physically with a ruler / caliper.

Edit `target_mm` and `test_speed` between runs to cover the
distance/speed grid (10/25/50/100/200 mm, 12 r/min for 25%, or
25 r/min for 50%).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from LinearMotorController import LinearMotorController  # noqa: E402


def main():
    """Return to home, settle, run a single forward move, report."""
    serial_port = "/dev/ttyUSB0"

    # ----- Edit these between trials -----
    target_mm = 200.0  # 10, 25, 50, 100, 200
    test_speed = 12  # 12 = 25% of default 50, 25 = 50% of default
    settle_seconds = 3.0
    # --------------------------------------

    lmc = LinearMotorController(serial_port) # serial 통신 

    print(f"--- Trial: target {target_mm} mm @ speed {test_speed} r/min ---") # serial 통신 성공 시 성공 확인 print문

    startup_wait_s = 10 # 혼자 측정해서 10초 대기 후 진행
    print(f"Starting in {startup_wait_s} s — get into observation position.") # 해당 문구 print 후 startup_wait_s만큼 카운트 후 46번 라인부터 실행
    for remaining in range(startup_wait_s, 0, -1):
        print(f"  {remaining} ...", end="\r", flush=True)
        time.sleep(1)
    print("  start!     ")

    # 원점 복귀 코드: 전원을 킨 시점의 Rail의 위치가 원점이므로 양 끝에 위치시키고 작동하길 권장함. (시작점에 놓을 시 +값으로, 끝점에 놓을 시 -로 이동변위 입력)
    print("Returning to origin (0 mm) via closed loop ...") # 시작 전 print
    home_pos = lmc.move_to_mm(0.0) # encoder 기준 0.0(원점)으로 이동
    if home_pos is None: # 예외처리: 
        print("FAIL: could not return to origin.")
        return 1
    print(f"  Origin reached: {home_pos:+.4f} mm")

    print(f"Settling for {settle_seconds} s ...")
    time.sleep(settle_seconds) # 역시 바로 진행하면 혼자 측정시 힘들기 때문에 settle_second만큼 대기

    pre_move = lmc.read_position_mm()
    print(f"Pre-move position: {pre_move:+.4f} mm")

    # 역시 클로드가 맘대로 넣어준 print 문구니 거슬리면 없에줍시다(61~63 line)
    print( 
        f"Moving +{target_mm} mm relative at {test_speed} r/min"
        f" (single speed, no closed-loop correction) ..."
    )
    # 60 s timeout covers 200 mm at the slowest tested speed (12 r/min)
    # with margin. Default 10 s would otherwise stop the move early.
    final = lmc.move_relative_mm(target_mm, speed=test_speed, timeout=60.0) # timeout은 넉넉히 줍시다(15.0주니 200mm이동 시 157mm밖에 이동안함)
    if final is None: # 에외처리
        print("FAIL: move_relative_mm returned None.")
        return 1

    delta = final - pre_move
    print()
    print("=== Result ===")
    print(f"  Final encoder position: {final:+.4f} mm") # encoder에서 최종적으로 기록된 거리
    print(f"  Travel from origin:     {delta:+.4f} mm") # 원점기준 움직인 거리
    print(f"  Encoder error vs target: {delta - target_mm:+.4f} mm") # error
    print()
    print("  Now measure physically with a ruler / caliper and record") # 클로드가 ㅈ대로 짠거니 삭제하셔도 무방합니다
    print("  both the encoder reading and the physical reading in the")
    print("  CSV under the appropriate Trial column.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

from weight_reader import WeightReader
import time

# ============== CONFIG ==============
STABILITY_THRESHOLD = 0.0005
STABLE_READINGS = 3
ZERO_RESET = 0.0005
MIN_VALID_WEIGHT = 0.0001
ZERO_CONFIRM_READINGS = 2
NO_CHANGE_TIMEOUT = 0.5  # REDUCED from 1.5 to 0.5 seconds
# ====================================

def main():
    reader = WeightReader(port="COM5", baudrate=9600)
    reader.start()

    try:
        print("\n⚖️  WEIGHING MACHINE\n")

        max_weight = 0.0
        stable_counter = 0
        is_measuring = False
        last_weight_change_time = time.time()
        weight_increased_since_max = False
        zero_counter = 0
        weight_displayed = False

        while True:
            weight = reader.get_weight(smoothed=True)

            if weight is None:
                time.sleep(0.01)
                continue

            if abs(weight) < ZERO_RESET:
                zero_counter += 1
                
                if zero_counter >= ZERO_CONFIRM_READINGS and is_measuring and weight_displayed:
                    max_weight = 0.0
                    stable_counter = 0
                    is_measuring = False
                    weight_increased_since_max = False
                    zero_counter = 0
                    weight_displayed = False
                
                time.sleep(0.01)
                continue
            else:
                zero_counter = 0

            if weight < MIN_VALID_WEIGHT:
                time.sleep(0.01)
                continue

            if not is_measuring:
                is_measuring = True
                weight_displayed = False
                last_weight_change_time = time.time()

            if abs(weight - max_weight) > STABILITY_THRESHOLD:
                max_weight = weight
                stable_counter = 0
                weight_increased_since_max = False
                last_weight_change_time = time.time()
                weight_displayed = False

            elif abs(weight - max_weight) <= STABILITY_THRESHOLD:
                weight_increased_since_max = True
                stable_counter += 1

            else:
                stable_counter = 0
                weight_increased_since_max = False

            if is_measuring and not weight_displayed:
                time_since_change = time.time() - last_weight_change_time
                
                if time_since_change >= NO_CHANGE_TIMEOUT:
                    if stable_counter >= STABLE_READINGS and weight_increased_since_max:
                        final_weight_grams = round(max_weight * 1000, 1)
                        print(f"{final_weight_grams}g")
                        weight_displayed = True

            time.sleep(0.01)

    except KeyboardInterrupt:
        print()

    finally:
        reader.stop()


if __name__ == "__main__":
    main()
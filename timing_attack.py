import time
import statistics
from crypto_verify import verify_payload_authenticity

def measure_timing(payload, signature, iterations=5000):
    times = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        verify_payload_authenticity(payload, signature)
        end = time.perf_counter_ns()
        times.append(end - start)
    return times

def run_test():
    print('[+] Starting Side-Channel Timing Analysis for Caseit2u2 Secure Labs...')
    payload = b'Omnichain_Asset_Transfer_Data'
    valid_sig = 'ETB_SAMPLE_SIGNATURE'
    invalid_sig = 'FORGED_SIGNATURE_DATA'
    print('Running 5000 iterations per test case...')
    v_times = measure_timing(payload, valid_sig)
    i_times = measure_timing(payload, invalid_sig)
    avg_v = statistics.mean(v_times)
    avg_i = statistics.mean(i_times)
    diff = abs(avg_v - avg_i)
    print('\n[+] Audit Results:')
    print(f'  Average Time (Valid):   {avg_v:.2f} ns')
    print(f'  Average Time (Invalid): {avg_i:.2f} ns')
    print(f'  Average Delta:          {diff:.2f} ns')
    if diff < 1000:
        print('\n[VERIFICATION SUCCESSFUL] Constant-Time HMAC logic is operational.')
    else:
        print('\n[WARNING] Statistical timing variance detected.')

if __name__ == "__main__":
    run_test()

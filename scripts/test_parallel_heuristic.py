from dou_snaptrack.utils.parallel import recommend_parallel
import os

if __name__ == '__main__':
    saved = os.cpu_count
    try:
        for cores in [2,4,8,16,24,32]:
            os.cpu_count = lambda: cores  # type: ignore
            for jobs in [1,2,4,8,16,32]:
                print(f'cores={cores} jobs={jobs} ->', recommend_parallel(jobs, prefer_process=True))
    finally:
        os.cpu_count = saved  # type: ignore

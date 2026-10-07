import time

def get_execution_time(func):
  start_time = time.perf_counter()
  result = func()
  end_time = time.perf_counter()
  return [result, end_time - start_time]
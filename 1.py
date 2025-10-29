import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, parse_qsl
from urllib.parse import quote
import time
import threading
from datetime import datetime
import random
import pytz
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore, Style, init
import re
import html


# Khởi tạo colorama
init(autoreset=True)

web_link = 'https://namgay.com/'

# Đặt timezone về Asia/Ho_Chi_Minh
timezone = pytz.timezone("Asia/Ho_Chi_Minh")



# Hàm để lưu dữ liệu CRON vào API sau khi hoàn thành
def save_cron_data(id_cron, output, status, timeout):
    current_time_str = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
    timeout = round(timeout, 2)
    api_url = f"{web_link}api/edit_task.php"  # Sử dụng web_link đã được nhập
    payload = {
        'id': id_cron,
        'status': status,
        'timeout': timeout,
        'output': output
    }

    retries = 0
    success = False
    max_retries = 5 # Tối đa thử lại 5 lần khi thất bại
    while retries < max_retries and not success:
        try:
            response = requests.post(api_url, data=payload)
            if response.status_code == 200:
                print(f"[{current_time_str}] Lưu CRON [{id_cron}] ({status} - {timeout}s)")
                success = True
            else:
                print(f"[{current_time_str}] Không thể lưu dữ liệu cho CRON ID {id_cron}: {response.status_code}")
        except Exception as e:
            print(f"[{current_time_str}] Lỗi khi lưu dữ liệu cho CRON ID {id_cron}: {e}")

        if not success:
            retries += 1
            if retries < max_retries:
                print(f"[{current_time_str}] Thử lại lần {retries}/{max_retries} sau 2 giây...")
                time.sleep(2)  # Đợi 2 giây trước khi thử lại
            else:
                print(f"[{current_time_str}] Thử lại thất bại sau {max_retries} lần.")

# Danh sách User-Agent
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36 Edg/116.0.1926.62",
]

# Hàm để chạy từng CRON task
def run_cron(link, method, id_cron, timeout_config):
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time_str}] Chạy CRON [{id_cron}] ({link} - Method {method})")
    
    try:
        start_time = time.time()  # Thời gian bắt đầu

        # Chọn ngẫu nhiên User-Agent từ danh sách
        headers = {
            "User-Agent": random.choice(user_agents)
        }
        link = html.unescape(link)  # Điều này sẽ thay thế &amp; bằng &
        
        # Xử lý method GET hoặc POST mà không phân tích URL
        if method == "GET":
            response = requests.get(link, headers=headers, timeout=timeout_config)
        elif method == "POST":
            response = requests.post(link, headers=headers, timeout=timeout_config)
        else:
            print(f"Phương thức {method} không được hỗ trợ.")
            return

        # Lấy dữ liệu phản hồi
        output = response.text
        status = response.status_code
        end_time = time.time()  # Thời gian kết thúc
        timeout = end_time - start_time  # Thời gian tải

        # Gọi hàm lưu dữ liệu sau khi cron xong
        save_cron_data(id_cron, output, status, timeout)  # Gửi timeout vào hàm lưu dữ liệu

    except requests.exceptions.Timeout as e:
        end_time = time.time()
        timeout = end_time - start_time
        error_output = f"Timeout error: {str(e)}"
        error_status = 408  # Request Timeout
        print(f"[{current_time_str}] Lỗi timeout khi chạy CRON {link} - {error_status}")
        save_cron_data(id_cron, error_output, error_status, timeout)

    except requests.exceptions.ConnectionError as e:
        end_time = time.time()
        timeout = end_time - start_time
        error_output = f"Connection error: {str(e)}"
        error_status = 503  # Service Unavailable
        print(f"[{current_time_str}] Lỗi kết nối khi chạy CRON {link} - {error_status}")
        save_cron_data(id_cron, error_output, error_status, timeout)

    except requests.exceptions.HTTPError as e:
        end_time = time.time()
        timeout = end_time - start_time
        error_output = f"HTTP error: {str(e)}"
        error_status = response.status_code  # Sử dụng mã trạng thái HTTP nếu có
        print(f"[{current_time_str}] Lỗi HTTP khi chạy CRON {link} - {error_status}")
        save_cron_data(id_cron, error_output, error_status, timeout)

    except Exception as e:
        end_time = time.time()
        timeout = end_time - start_time
        error_output = f"Unexpected error: {str(e)}"
        error_status = 500  # Internal Server Error
        print(f"[{current_time_str}] Lỗi không xác định khi chạy CRON {link} - {error_status}")
        save_cron_data(id_cron, error_output, error_status, timeout)


session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))
session.mount('http://', HTTPAdapter(max_retries=retries))

# Sử dụng ThreadPoolExecutor để chạy các CRON jobs
def fetch_tasks_and_run():
    # Tạo một ThreadPoolExecutor với tối đa 10 worker để chạy các tác vụ đồng thời
    with ThreadPoolExecutor(max_workers=3000) as executor:  # Số lượng tác vụ chạy đồng thời là 10
        existing_tasks = set()  # Tập hợp lưu trữ ID của các tác vụ đã được chạy
        while True:  # Vòng lặp vô hạn để liên tục lấy và thực thi các tác vụ từ API
            try:
                # Gửi yêu cầu GET tới API để lấy danh sách các tác vụ CRON
                url = f"{web_link}api/list_task.php"  # Sử dụng web_link đã được nhập
                response = session.get(url, timeout=10)  # Thời gian chờ tối đa cho phản hồi là 10 giây
                
                # Kiểm tra xem yêu cầu có thành công hay không (mã trạng thái HTTP 200 là thành công)
                if response.status_code == 200:
                    data = response.json()  # Chuyển đổi phản hồi JSON thành dictionary Python
                    
                    # Kiểm tra trạng thái của API phản hồi có là "success" hay không
                    if data["status"] == "success":
                        tasks = data["data"]  # Lấy danh sách các tác vụ từ API
                        
                        # Tạo một tập hợp chứa các ID của các tác vụ hiện tại từ API
                        current_tasks = set(task["id"] for task in tasks)

                        # Duyệt qua từng tác vụ trong danh sách tác vụ
                        for task in tasks:
                            # Nếu ID của tác vụ chưa có trong existing_tasks, nghĩa là đây là tác vụ mới
                            if task["id"] not in existing_tasks:
                                # Gửi tác vụ mới đến executor để chạy đồng thời
                                executor.submit(run_cron, task["link_cron"], task["method"], task["id"], task["timeout"])
                                # Thêm ID của tác vụ vào existing_tasks để tránh chạy lại
                                existing_tasks.add(task["id"])

                        # Kiểm tra và xóa các tác vụ đã bị xóa khỏi API nhưng vẫn còn trong existing_tasks
                        for task_id in list(existing_tasks):  # Duyệt qua từng task_id trong existing_tasks
                            # Nếu task_id không còn trong current_tasks (tức là API không trả về nữa)
                            if task_id not in current_tasks:
                                # Loại bỏ task_id khỏi existing_tasks
                                existing_tasks.remove(task_id)
                    else:
                        # In ra thông báo nếu API trả về lỗi (không phải "success")
                        print(f"Lỗi từ API: {data['msg']}")
                else:
                    # Nếu kết nối không thành công, in ra mã trạng thái HTTP
                    print(f"Lỗi khi kết nối API: {response.status_code}")
            except requests.exceptions.RequestException as e:
                # Bắt ngoại lệ nếu xảy ra lỗi kết nối và in ra thông báo lỗi
                print(f"Lỗi kết nối: {e}")

            # Chờ 1 giây trước khi tiếp tục lấy danh sách các tác vụ từ API (giảm tải cho API)
            time.sleep(1)

       
def print_ascii_art():
    art = """
    ░█████╗░███╗░░░███╗░██████╗███╗░░██╗████████╗░░░░█████╗░░█████╗░
    ██╔══██╗████╗░████║██╔════╝████╗░██║╚══██╔══╝░░░██╔══██╗██╔══██╗
    ██║░░╚═╝██╔████╔██║╚█████╗░██╔██╗██║░░░██║░░░░░░██║░░╚═╝██║░░██║
    ██║░░██╗██║╚██╔╝██║░╚═══██╗██║╚████║░░░██║░░░░░░██║░░██╗██║░░██║
    ╚█████╔╝██║░╚═╝░██║██████╔╝██║░╚███║░░░██║░░░██╗╚█████╔╝╚█████╔╝
    ░╚════╝░╚═╝░░░░░╚═╝╚═════╝░╚═╝░░╚══╝░░░╚═╝░░░╚═╝░╚════╝░░╚════╝░
    """
    print(Fore.CYAN + art)

def print_header():
    print(Fore.GREEN + "=" * 50)
    print(Fore.YELLOW + "[-] Project: CRONJOB")
    print(Fore.YELLOW + f"[-] Version: 1.0.0")
    print(Fore.GREEN + "=" * 50)



# Gọi hàm in chữ nghệ thuật
print_ascii_art()

# Hiển thị header thông tin dự án
print_header()


print(Fore.GREEN + "\nĐang khởi động tool, vui lòng đợi...")

# Gọi hàm fetch_tasks_and_run với link web từ người dùng nhập vào
fetch_tasks_and_run()

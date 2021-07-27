'''MainWindow Socket Client'''
# -*- coding: UTF-8 -*-

import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
import scrframe
import socket
import threading
import cv2
import pyaudio
import time
import inspect
import ctypes
import numpy
import zlib


#强行杀死一个线程
def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")
def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)


# create a server socket
PORT = 5050
# format of message
TYPE = 1 # 传输的信息类型
FILENAME = 64 # 文件传输的文件名长度
HEADER = 128 # 1/2号信息类型传输的长度
LIVE_TYPE = 1 # 视频聊天传输的流信息类型("1": audio; "2": video)
LIVE_HEADER = 2048 # 视频聊天一次传输的长度
# audio信息
CHUNK = 1024
FORMAT_AUDIO = pyaudio.paInt16
CHANNEL = 1
RATE = 22050
# 文本信息
FORMAT = 'utf-8'
DISCONNECT_MSG = "!disconnect"


class SelectFileWindow():
    def __init__(self, tk_window, main_conns, tk_win_par):
        self.parWin = tk_win_par
        # 已经连接的列表
        self.conns = main_conns
        # 选择文件窗口的属性
        self.root = tk_window
        self.root.title("Select Files")
            # 窗口图标的设置暂无
        self.root.minsize(395, 300)  # 最小尺寸
        self.root.maxsize(395, 300)  # 最大尺寸
        # 显示文件的frame和listbox
        self.fr_filenames = tk.Frame(self.root, bg="#ffecc7", width=360, height=250)
        self.fr_filenames.grid(row=1,column=0,padx=15)
        self.lbx_filenames = tk.Listbox(self.fr_filenames, width=50, height=13)
        self.lbx_filenames.grid(row=0,column=0)
        # 选择、删除文件的按钮
        self.fr_group_btn = tk.Frame(self.root, width=540, height=250)
        self.fr_group_btn.grid(row=0, column=0, padx=15)
        self.btn_add = tk.Button(self.fr_group_btn, text='+', width=8, command=self.btn_add_click)
        self.btn_add.grid(row=0, column=0)
        self.btn_erase = tk.Button(self.fr_group_btn, text='-', width=8,
                                   command=lambda x=self.lbx_filenames: x.delete(tk.ACTIVE))
        self.btn_erase.grid(row=0, column=1)
        self.btn_eraseAll = tk.Button(self.fr_group_btn, text='Clear', width=10, command=self.btn_eraseAll_click)
        self.btn_eraseAll.grid(row=0, column=2)
        self.lbl_temp1 = tk.Label(self.fr_group_btn, width=6).grid(row=0, column=3)
        # 发送全部文件的按钮
        self.btn_send = tk.Button(self.fr_group_btn, text='>>', width=13, command=self.btn_send_click)
        self.btn_send.grid(row=0, column=4)
    def btn_add_click(self):
        filename = filedialog.askopenfilename(title='Select File',initialdir='/',
                                              filetypes=(("Photo","*.jpg"),("All Files","*.*")))
        self.lbx_filenames.insert("end",filename)
    def btn_send_click(self):
        fileSize = self.lbx_filenames.size()
        if fileSize:
            # 显示自己的来源
            lbl_fileAddr = tk.Label(self.parWin.interior, text='ME', width=45, fg='#333333', bg='#ffecc7',
                                    wraplength=290, anchor='e', justify='right')
            lbl_fileAddr.pack(side='top', anchor='e')
            # 发送文件
            for i in range(0,fileSize):
                filename = self.lbx_filenames.get(i)
                # 发送文件
                with open(filename,'rb') as rf:
                    msg = rf.read()
                    # 发送信息
                    if self.conns:
                        conn=self.conns
                        # 发送信息类型
                        type_info = str("2").encode(FORMAT)
                        type_info += b" " * (TYPE - len(type_info))
                        conn.send(type_info)
                        # 发送文件的名字
                        name = filename.split("/")[-1].encode(FORMAT)
                        name_length = len(name)
                        name_info = str(name_length).encode(FORMAT)
                        name_info += b" " * (FILENAME - len(name_info))
                        conn.send(name_info)
                        conn.send(name)
                        # 发送文件的内容
                        msg_length = len(msg)
                        send_length = str(msg_length).encode(FORMAT)
                        send_length += b" " * (HEADER - len(send_length))
                        conn.send(send_length)
                        conn.send(msg)
                        # 在对话窗显示发送信息
                        lbl_fileMsg = tk.Label(self.parWin.interior, text=f'[FILE] {filename}', width=45,
                                               wraplength=290, anchor='e', justify='right')
                        lbl_fileMsg.pack(side='top', anchor='e')
                    else:
                        messagebox.showerror('ERROR', 'No one is connected!')
            self.lbx_filenames.delete(0,'end')
        else:
            messagebox.showwarning('WARNING', 'No files!')
    def btn_eraseAll_click(self):
        self.lbx_filenames.delete(0,'end')


class MainWindow():
    def __init__(self, tk_window):
        # socket建立的各连接(conn,addr)
        self.conns = None
        self.connected = False
        self.live_check = False
        # 窗口的属性
        self.root = tk_window
        self.root.title("ZConn_C")
        self.root["background"] = "#ffecc7"
        self.root.iconphoto(False, tk.PhotoImage(file='dushu.png'))
        self.root.minsize(600, 488)  # 最小尺寸
        self.root.maxsize(600, 488)  # 最大尺寸
        # 与ipv4连接
        self.fr_group_ipv4 = tk.Frame(self.root,width=540,height=350)
        self.fr_group_ipv4.grid(row=0, column=0, padx=15)
        self.lbl_IPV4 = tk.Label(self.fr_group_ipv4, text='IPV4: ', width=10)
        self.lbl_IPV4.grid(row=0, column=0)
        self.txt_IPV4 = tk.Entry(self.fr_group_ipv4, width=20)
        self.txt_IPV4.grid(row=0, column=1)
        self.lbl_temp1 = tk.Label(self.fr_group_ipv4,width=2)
        self.lbl_temp1.grid(row=0,column=2)
        self.btn_conn = tk.Button(self.fr_group_ipv4, text="CONNECT", width=20,command=self.socket_start)
        self.btn_conn.grid(row=0, column=3)
        self.btn_disconn = tk.Button(self.fr_group_ipv4, text="DISCONNECT", width=20,command=self.btn_disconn_click)
        self.btn_disconn.grid(row=0, column=4)
        # 消息显示窗口 /调包scrframe，带滚动条的frame
        self.fr_message = scrframe.VerticalScrolledFrame(self.root,width=540, height=350)
        self.fr_message.grid(row=1,column=0,padx=15)
        self.fr_message.propagate(0)
        # 任务管理器选文件、视频音频
        self.fr_group_btn = tk.Frame(self.root,width=540,height=350)
        self.fr_group_btn.grid(row=2,column=0, padx=15)
        self.btn_file = tk.Button(self.fr_group_btn, text='FILE', width=30, command=self.selectFile)
        self.btn_file.grid(column=0,row=0)
        #self.btn_audio = tk.Button(self.fr_group_btn, text='AUDIO', width=20)
        #self.btn_audio.grid(column=1,row=0)
        self.btn_video = tk.Button(self.fr_group_btn, text='VIDEO', width=30, command=self.btn_video_click)
        self.btn_video.grid(column=2,row=0)
        # 文字消息、发送消息按钮
        self.fr_group_sendText = tk.Frame(self.root,width=540,height=350)
        self.fr_group_sendText.grid(row=3,column=0, padx=15, pady=1)
        self.txt_textBox = tk.Text(self.fr_group_sendText, width=60, height=5)
        self.txt_textBox.grid(row=0, column=0, columnspan=3)
        self.btn_sendText = tk.Button(self.fr_group_sendText, text='>>', width=20,height=3,
                                      command=self.btn_sendText_click)
        self.btn_sendText.grid(row=0, column=3)
        # 音频
        self.p_play = pyaudio.PyAudio()
        self.p_record = pyaudio.PyAudio()
        self.p_play.get_default_output_device_info()
        self.p_record.get_default_input_device_info()
    # client开始连接
    def socket_start(self):
        SERVER = self.txt_IPV4.get()
        ADDRESS = (SERVER, PORT)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(ADDRESS)
        self.connected = True
        self.conns = client # 为接受client的消息开一个单独线程
        self.thread = threading.Thread(target=self.handleRecv,args=(client,SERVER))
        self.thread.start()
        messagebox.showinfo(title='Client',message='Connected!')
    # server文字消息的发送
    def btn_sendText_click(self):
        # 获取输入框信息并删除
        msg = self.txt_textBox.get('0.0','end').rstrip('\n')
        self.txt_textBox.delete('0.0','end')
        # 发送信息
        if self.conns:
            if msg:
                # 发送信息类型
                type_info = str("1").encode(FORMAT)
                type_info += b" " * (TYPE - len(type_info))
                self.conns.send(type_info)
                # 发送文字信息
                message = msg.encode(FORMAT)
                msg_length = len(message)
                send_length = str(msg_length).encode(FORMAT)
                send_length += b" " * (HEADER - len(send_length))
                self.conns.send(send_length)
                self.conns.send(message)
                # 在窗口上显示自己发的消息
                lbl_textAddr = tk.Label(self.fr_message.interior, text='ME', width=45, fg='#333333', bg='#ffecc7',
                                        wraplength=290, anchor='e', justify='right')
                lbl_textAddr.pack(side='top', anchor='e')
                lbl_textMsg = tk.Label(self.fr_message.interior, text=msg, width=45,
                                       wraplength=290, anchor='e', justify='right')
                lbl_textMsg.pack(side='top', anchor='e')
            else:
                messagebox.showwarning('WARNING', 'Message is empty!')
        else:
            messagebox.showerror('ERROR','No one is connected!')
    # 接受client的消息
    def handleRecv(self,conn,addr):
        self.connected = True
        while self.connected:
            # 受到的信息类型
            type = conn.recv(TYPE).decode(FORMAT)
            type = int(type)
            # 地址来源信息
            msg_addr = f"From [{addr}]: "
            lbl_textAddr = tk.Label(self.fr_message.interior, text=msg_addr, width=45, fg='#706c61', bg='#ffecc7',
                                    wraplength=290, anchor='w', justify='left')
            lbl_textAddr.pack(side='top', anchor='w')
            # 文本信息类型
            if type == 1:
                msg_length = conn.recv(HEADER).decode(FORMAT)
                msg_length = int(msg_length)
                msg = conn.recv(msg_length).decode(FORMAT)
                if msg == DISCONNECT_MSG:
                    break
                lbl_textMsg = tk.Label(self.fr_message.interior, text=msg, width=45,
                                       wraplength=290, anchor='w', justify='left')
                lbl_textMsg.pack(side='top', anchor='w')
            # 文件信息类型
            elif type == 2:
                # 文件名
                name_length = conn.recv(FILENAME).decode(FORMAT)
                name_length = int(name_length)
                name = conn.recv(name_length).decode(FORMAT)
                # 文件内容
                msg_length = conn.recv(HEADER).decode(FORMAT)
                msg_length = int(msg_length)
                msg = conn.recv(msg_length)
                tempLen = len(msg)
                while tempLen < int(msg_length):
                    msg += conn.recv(int(msg_length) - tempLen)
                    tempLen = len(msg)
                # 接受文件的记录
                lbl_fileInfo = tk.Label(self.fr_message.interior, text=f'[FILE] {name}', width=45,
                                        wraplength=290, anchor='w', justify='left')
                lbl_fileInfo.pack(side='top', anchor='w')
                # 写至本地
                with open(name, "wb") as rf:
                    rf.write(msg)
                    messagebox.showinfo(title='Save File', message='Successfully!')
            # 发起视频消息类型
            elif type == 3:
                self.live_check_s = False
                self.live_check = False
                # 发送的线程
                thread_send = threading.Thread(target=self.send_live)
                thread_send.start()
                #
                tStart = time.time()
                tEnd = 0
                # 播放设备
                self.p_play = pyaudio.PyAudio()
                self.p_play.get_default_output_device_info()
                stream_play = self.p_play.open(format=FORMAT_AUDIO, channels=CHANNEL, rate=RATE, output=True)
                # 接收
                liveMsg_type = 0
                while (self.connected):
                    liveMsg_type = conn.recv(LIVE_TYPE).decode(FORMAT)
                    liveMsg_type = int(liveMsg_type)
                    # audio
                    if liveMsg_type == 1:
                        # 信息的长度
                        msg_length = conn.recv(HEADER).decode(FORMAT)
                        tempLen = len(msg_length)
                        while tempLen < HEADER:
                            a = conn.recv(HEADER - tempLen).decode(FORMAT)
                            msg_length += a
                            tempLen = len(msg_length)
                        # 信息
                        if msg_length:
                            msg = conn.recv(int(msg_length))
                            tempLen = len(msg)
                            while tempLen < int(msg_length):
                                msg += conn.recv(int(msg_length)-tempLen)
                                tempLen = len(msg)
                            data = zlib.decompress(msg)
                            stream_play.write(data)
                    # video
                    elif liveMsg_type == 2:
                        # 信息的长度
                        msg_length = conn.recv(LIVE_HEADER).decode(FORMAT)
                        tempLen = len(msg_length)
                        while tempLen < LIVE_HEADER:
                            a = conn.recv(LIVE_HEADER - tempLen).decode(FORMAT)
                            msg_length += a
                            tempLen = len(msg_length)
                        # 信息
                        if msg_length:
                            msg = conn.recv(int(msg_length))
                            tempLen = len(msg)
                            while tempLen<int(msg_length):
                                msg += conn.recv(int(msg_length)-tempLen)
                                tempLen = len(msg)
                            data = numpy.fromstring(msg, dtype='uint8')
                            frame = cv2.imdecode(data, 1)
                            cv2.imshow(f'From client {addr}', frame)
                            if cv2.waitKey(10) & 0xFF == ord('q'):
                                self.live_check = True
                    # client先停止
                    elif liveMsg_type == 5:
                        tEnd = time.time()
                        messagebox.showinfo(title='Info', message=f'{addr} finished the talk.')
                        break
                    time.sleep(0.015)  # 由于waitKey!=sleep，因此必不可少...时长有待商榷==0.025
                    if self.live_check:
                        break
                # 退出，销毁窗口，显示聊天信息
                self.live_check_s = True
                if not tEnd:
                    tEnd = time.time()
                tCost = tStart - tEnd
                # 停止录音
                stream_play.stop_stream()
                stream_play.close()
                self.p_play.terminate()
                # 停止视频
                cv2.destroyAllWindows()
                lbl_liveInfo = tk.Label(self.fr_message.interior, text=f'[Live Time] {round(tCost, 2)}s', width=45,
                                        fg='#333333', bg='#ffffff', wraplength=290, anchor='w', justify='left')
                lbl_liveInfo.pack(side='top', anchor='w')
                # 处理还client未断掉时发送的多余的数据
                while (liveMsg_type == 1 or liveMsg_type == 2):
                    liveMsg_type = conn.recv(LIVE_TYPE).decode(FORMAT)
                    liveMsg_type = int(liveMsg_type)
                    # audio
                    if liveMsg_type == 1:
                        # 信息长度
                        msg_length = conn.recv(HEADER).decode(FORMAT)
                        tempLen = len(msg_length)
                        while tempLen < HEADER:
                            a = conn.recv(HEADER - tempLen).decode(FORMAT)
                            msg_length += a
                            tempLen = len(msg_length)
                        # 信息
                        if msg_length:
                            msg = conn.recv(int(msg_length))
                            tempLen = len(msg)
                            while tempLen<int(msg_length):
                                msg += conn.recv(int(msg_length)-tempLen)
                                tempLen = len(msg)
                    # video
                    elif liveMsg_type == 2:
                        # 信息长度
                        msg_length = conn.recv(LIVE_HEADER).decode(FORMAT)
                        tempLen = len(msg_length)
                        while tempLen < LIVE_HEADER:
                            a = conn.recv(LIVE_HEADER - tempLen).decode(FORMAT)
                            msg_length += a
                            tempLen = len(msg_length)
                        # 信息
                        if msg_length:
                            msg = conn.recv(int(msg_length))
                            tempLen = len(msg)
                            while tempLen<int(msg_length):
                                msg += conn.recv(int(msg_length)-tempLen)
                                tempLen = len(msg)
                    # client已停止
                    elif liveMsg_type == 5:
                        break
                    time.sleep(0.005)
        messagebox.showinfo('Disconnect',message=f"{addr} disconnect!")
        conn.close()
    # server文件消息的发送
    def selectFile(self):
        root = tk.Tk()
        SelectFileWindow(root,self.conns,self.fr_message)
        root.wm_attributes('-topmost', 1) # 固定窗口在最上方
        root.mainloop()
    # 开始视频电话的按钮
    def btn_video_click(self):
        self.live_check = False
        # 接受另一端视频信息的线程
        thread_recv = threading.Thread(target=self.recv_live)
        thread_recv.start()
        # 发送
        type_info = str("3").encode(FORMAT)
        type_info += b" " * (TYPE - len(type_info))
        self.conns.send(type_info)
        # 显示自己发起视频的信息
        lbl_textAddr = tk.Label(self.fr_message.interior, text='ME', width=45, fg='#333333', bg='#ffecc7',
                                wraplength=290, anchor='e', justify='right')
        lbl_textAddr.pack(side='top', anchor='e')
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        tStart = time.time()
        # 录音设备
        self.p_record = pyaudio.PyAudio()
        self.p_record.get_default_input_device_info()
        stream_record = self.p_record.open(format=FORMAT_AUDIO, channels=CHANNEL, rate=RATE, input=True,
                                      frames_per_buffer=CHUNK)
        while not self.live_check:
            # 音频
            data = stream_record.read(CHUNK, exception_on_overflow=False)
            self.send_audio(self.conns, data)
            # 视频
            ret, frame = cap.read()
            frame = cv2.resize(frame, (0, 0), fx=0.3, fy=0.3, interpolation=cv2.INTER_CUBIC)
            cv2.imshow('Me', frame)
            img = self.to_img(frame)
            self.send_video(self.conns, img)
            if cv2.waitKey(10) & 0xFF == ord('q'):
                self.live_check = True
            # 音频
            data = stream_record.read(CHUNK, exception_on_overflow=False)
            self.send_audio(self.conns, data)
        # 发送end标识=5，标识到达末尾
        live_type = str("5").encode(FORMAT)
        live_type += b" " * (LIVE_TYPE - len(live_type))
        self.conns.send(live_type)
        # 退出，销毁窗口，显示聊天信息
        # 停止录音
        stream_record.stop_stream()
        stream_record.close()
        self.p_record.terminate()
        # 停止视频
        cap.release()
        cv2.destroyAllWindows()
        tEnd = time.time()
        tCost = tStart - tEnd
        lbl_textMsg = tk.Label(self.fr_message.interior, text=f'[Live Time] {round(tCost, 2)}s', width=45,
                               wraplength=290, anchor='e', justify='right')
        lbl_textMsg.pack(side='top', anchor='e')
    # 发送视频
    def send_video(self,conn,frame):
        # 发送信息类型
        live_type = str("2").encode(FORMAT)
        live_type += b" " * (LIVE_TYPE - len(live_type))
        conn.send(live_type)
        # 发送信息
        msg_length = len(frame)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b" " * (LIVE_HEADER - len(send_length))
        conn.send(send_length)
        conn.send(frame)
    # 发送音频
    def send_audio(self,conn,msg):
        # 发送信息类型
        live_type = str("1").encode(FORMAT)
        live_type += b" " * (LIVE_TYPE - len(live_type))
        conn.send(live_type)
        # 发送信息
        data = zlib.compress(msg)
        msg_length = len(data)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b' ' * (HEADER - len(send_length))
        conn.send(send_length)
        conn.send(data)
    # 取消连接
    def btn_disconn_click(self):
        type_info = str("1").encode(FORMAT)
        type_info += b" " * (TYPE - len(type_info))
        self.conns.send(type_info)
        # 发送文字信息
        message = DISCONNECT_MSG.encode(FORMAT)
        msg_length = len(message)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b" " * (HEADER - len(send_length))
        self.conns.send(send_length)
        self.conns.send(message)
        self.connected = False
        stop_thread(self.thread)
        self.conns = None
    def to_img(self, frame):
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
        img_encode = cv2.imencode('.jpg', frame, encode_param)[1]
        data = numpy.array(img_encode)
        stringData = data.tostring()
        return stringData
    def send_live(self):
        # create a server socket
        PORT_s = 1234
        SERVER = self.txt_IPV4.get()
        ADDRESS_s = (SERVER, PORT_s)
        client_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_s.connect(ADDRESS_s)
        conn = client_s
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        # 录音设备
        self.p_record = pyaudio.PyAudio()
        self.p_record.get_default_input_device_info()
        stream_record = self.p_record.open(format=FORMAT_AUDIO, channels=CHANNEL, rate=RATE, input=True,
                                           frames_per_buffer=CHUNK)
        while not self.live_check_s:
            # 音频
            data = stream_record.read(CHUNK, exception_on_overflow=False)
            self.send_audio(conn, data)
            # 视频
            ret, frame = cap.read()
            frame = cv2.resize(frame, (0, 0), fx=0.3, fy=0.3, interpolation=cv2.INTER_CUBIC)
            cv2.imshow('Me', frame)
            img = self.to_img(frame)
            self.send_video(conn, img)
            cv2.waitKey(10)
            # 音频
            data = stream_record.read(CHUNK, exception_on_overflow=False)
            self.send_audio(conn, data)
        # 发送end标识=5，标识到达末尾
        live_type = str("5").encode(FORMAT)
        live_type += b" " * (LIVE_TYPE - len(live_type))
        conn.send(live_type)
        conn.close()
        # 停止录音
        stream_record.stop_stream()
        stream_record.close()
        self.p_record.terminate()
        # 停止视频
        cap.release()
        cv2.destroyAllWindows()
    def recv_live(self):
        # create a new socket
        PORT_r = 1234
        SERVER_r = socket.gethostbyname(socket.gethostname())
        ADDRESS_r = (SERVER_r, PORT_r)
        server_r = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_r.bind(ADDRESS_r)
        server_r.listen()
        conn, addr = server_r.accept()
        # 播放设备
        pr_play = pyaudio.PyAudio()
        pr_play.get_default_output_device_info()
        stream_play = pr_play.open(format=FORMAT_AUDIO, channels=CHANNEL, rate=RATE, output=True)
        # 开始接受
        liveMsg_type = 0
        self.live_check_r = False
        while not self.live_check_r:
            time.sleep(0.001) #
            liveMsg_type = conn.recv(LIVE_TYPE).decode(FORMAT)
            liveMsg_type = int(liveMsg_type)
            # audio
            if liveMsg_type == 1:
                # 消息的长度
                msg_length = conn.recv(HEADER).decode(FORMAT)
                tempLen = len(msg_length)
                while tempLen < HEADER:
                    a = conn.recv(HEADER - tempLen).decode(FORMAT)
                    msg_length += a
                    tempLen = len(msg_length)
                # 接收消息
                if msg_length:
                    msg = conn.recv(int(msg_length))
                    tempLen = len(msg)
                    while tempLen < int(msg_length):
                        msg += conn.recv(int(msg_length) - tempLen)
                        tempLen = len(msg)
                    data = zlib.decompress(msg)
                    stream_play.write(data)
            # video
            elif liveMsg_type == 2:
                # 接收消息的长度
                msg_length = conn.recv(LIVE_HEADER).decode(FORMAT)
                tempLen = len(msg_length)
                while tempLen < LIVE_HEADER:
                    a = conn.recv(LIVE_HEADER - tempLen).decode(FORMAT)
                    msg_length += a
                    tempLen = len(msg_length)
                # 接收的消息
                if msg_length:
                    msg = conn.recv(int(msg_length))
                    tempLen = len(msg)
                    while tempLen < int(msg_length):
                        msg += conn.recv(int(msg_length) - tempLen)
                        tempLen = len(msg)
                    data = numpy.fromstring(msg, dtype='uint8')
                    frame = cv2.imdecode(data, 1)
                    cv2.imshow(f'From {addr}', frame)
                    cv2.waitKey(10)
                    # if cv2.waitKey(10) & 0xFF == ord('q'):
                        # self.live_check_r = True
            # client先停止
            elif liveMsg_type == 5:
                break
            time.sleep(0.015)
            if self.live_check_r:
                break
        # 停止录音
        stream_play.stop_stream()
        stream_play.close()
        self.p_play.terminate()
        # 停止视频
        cv2.destroyAllWindows()
        # 处理还client未断掉时发送的多余的数据
        while (liveMsg_type == 1 or liveMsg_type == 2):
            liveMsg_type = conn.recv(LIVE_TYPE).decode(FORMAT)
            liveMsg_type = int(liveMsg_type)
            # audio
            if liveMsg_type == 1:
                # 信息长度
                msg_length = conn.recv(HEADER).decode(FORMAT)
                tempLen = len(msg_length)
                while tempLen < HEADER:
                    a = conn.recv(HEADER - tempLen).decode(FORMAT)
                    msg_length += a
                    tempLen = len(msg_length)
                # 信息
                if msg_length:
                    msg = conn.recv(int(msg_length))
                    tempLen = len(msg)
                    while tempLen < int(msg_length):
                        msg += conn.recv(int(msg_length) - tempLen)
                        tempLen = len(msg)
            # video
            elif liveMsg_type == 2:
                msg_length = conn.recv(LIVE_HEADER).decode(FORMAT)
                tempLen = len(msg_length)
                while tempLen < LIVE_HEADER:
                    a = conn.recv(LIVE_HEADER - tempLen).decode(FORMAT)
                    msg_length += a
                    tempLen = len(msg_length)
                if msg_length:
                    msg = conn.recv(int(msg_length))
                    tempLen = len(msg)
                    while tempLen < int(msg_length):
                        msg += conn.recv(int(msg_length) - tempLen)
                        tempLen = len(msg)
            # client已停止
            elif liveMsg_type == 5:
                break



def gui_main():
    root = tk.Tk()
    mWin = MainWindow(root)
    # 主线程窗口的消息循环
    root.mainloop()
if __name__=="__main__":
    gui_main()

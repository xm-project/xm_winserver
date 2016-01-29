#!/usr/bin/env python
#encoding:utf8
'''
Created on 2014-10-1

@author: Luke Liao thx robin1001
'''
import rospy
import socket
import struct
import threading
import sys
from xm_msgs.srv import *
from xm_msgs.msg import *
from std_msgs.msg import *

class XM_winserver:
    WIN_IP = '192.168.1.110'
    SELF_PORT = 10000
    SPEECH_PORT = 10000
    KINECT_PORT = 10004
    FACE_PORT = 10002
    def __init__(self):
        #XM_winserver.WIN_IP = rospy.get_param("win_ip")
        #XM_winserver.SELF_PORT = rospy.get_param("self_port")
        #XM_winserver.SPEECH_PORT = rospy.get_param("speech_port")
        #XM_winserver.FACE_PORT = rospy.get_param("face_port")
        #XM_winserver.KINECT_PORT = rospy.get_param("kinect_port")

        self.speech_pub = rospy.Publisher('task_comming', xm_Task)
        self.kinect_srv = rospy.Service('kinect_srv', xm_KinectSrv, self.kinect_srv_handler)
        self.face_srv = rospy.Service('face_srv', xm_FaceSrv, self.face_srv_handler)
        self.speech_sub = rospy.Subscriber('tts_data', xm_TTSNum, self.speech_callback)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(('', XM_winserver.SELF_PORT))

    def start(self):
        print 'xm_winserver start...'
        print 'tts server info %s:%d' % (XM_winserver.WIN_IP, XM_winserver.SPEECH_PORT)
        print 'face server info %s:%d' % (XM_winserver.WIN_IP, XM_winserver.FACE_PORT)
        print 'kinect server info %s:%d' % (XM_winserver.WIN_IP, XM_winserver.KINECT_PORT)
        #start win server
        t=threading.Thread(target = self.start_winserver)
        t.setDaemon(True)
        t.start()
        #start ros loop
        rospy.spin()

    def start_winserver(self):
        self.server.listen(10)
        while not rospy.is_shutdown():
            sock, addr = self.server.accept()
            print "connect coming"
            t = threading.Thread(target=self.handle_connect, args=(sock, addr))
            t.setDaemon(True)
            t.start()

    def recv_len(self, sock, length):
        data = []
        left = length
        while left != 0:
            tmp = sock.recv(left)
            data.append(tmp)
            left -= len(tmp)
        return ''.join(data)

    def _send_helper(self, ip, port, data):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((ip, port))
            data_len = struct.pack('!i', len(data))
            sock.sendall(data_len + data)
        except socket.error, ex:
            print socket.error, ex
        return sock

    def _send(self, ip, port, data):
        self._send_helper(ip, port, data).close()

    #send and wait return data
    def _send_wait(self, ip, port, data):
        sock = self._send_helper(ip, port, data)
        length, = struct.unpack('!i', self.recv_len(sock, 4))
        data = self.recv_len(sock, length)
        sock.close()
        return data

    def handle_connect(self, sock, addr):
        length, cmd = struct.unpack('!ib', self.recv_len(sock, 5))
        task = xm_Task()
        if cmd == 0x01:
            task.task_name.data = 'follow'
            status, = struct.unpack('!b', self.recv_len(sock, 1))
            task.status = status
            if status == 0x01:
                len_, = struct.unpack('!i', self.recv_len(sock, 4))
                name = self.recv_len(sock, len_)
                task.latched_str.data = name
        elif cmd == 0x02:
            task.task_name.data = 'whoiswho'
            status, = struct.unpack('!b', self.recv_len(sock, 1))
            task.status = status
            len_, = struct.unpack('!i', self.recv_len(sock, 4))
            name = self.recv_len(sock, len_)
            task.latched_str.data = name
        elif cmd == 0x03:
            task.task_name.data = 'shopping'
            status, = struct.unpack('!b', self.recv_len(sock, 1))
            task.status = status
            if status != 0x02:# except the follow order
                len_, = struct.unpack('!i', self.recv_len(sock, 4))
                name = self.recv_len(sock, len_)
                task.latched_str.data = name
        elif cmd == 0x06:
            task.task_name.data = 'GPSR'
            status, = struct.unpack('!b', self.recv_len(sock, 1))
            task.status = status
            if status != 0x05: # except the placing order
                len_, = struct.unpack('!i', self.recv_len(sock, 4))
                name = self.recv_len(sock, len_)
                task.latched_str.data = name
        print task
        self.speech_pub.publish(task)

    def speech_callback(self, msg):
        print 'new speech cmd arrived: ', msg.ttsnum
        speech = struct.pack('!bb', 0x01, msg.ttsnum)
        self._send(XM_winserver.WIN_IP,XM_winserver.SPEECH_PORT, speech)


    def kinect_srv_handler(self, request):
        print 'new kinect request arrived'
        rep = xm_KinectSrvResponse()
        if request.cmd != 0x03:
            send_data = struct.pack('!bi', request.cmd, len(request.req_name.data)) + request.req_name.data
        else :
            send_data = struct.pack('!b', request.cmd)
        # execution failed send the command again
        recv_data = self._send_wait(XM_winserver.WIN_IP, XM_winserver.KINECT_PORT, send_data)
        cmd, status, = struct.unpack('!bb', recv_data[:2])
        if status == 0x00 : # no people in the frame
            rep.rep_name.data = 'noperson'
            return rep
        if request.cmd == 0x01:
            return rep
        elif request.cmd == 0x02:
            print "fsdf"
            rep.position.x, rep.position.y, rep.position.z, rep.bel, = struct.unpack('4f', recv_data[2:])
            rep.position.x = rep.position.x - 0.2
            return rep
        elif request.cmd == 0x03:
            rep.position.x, rep.position.y, rep.position.z, = struct.unpack('3f', recv_data[2:14])
            print rep.position.x, rep.position.y, rep.position.z
            len_, = struct.unpack('!i', recv_data[14:18])
            print len_
            rep.rep_name.data = recv_data[18: 18 + len_]
            print rep.rep_name.data
            rep.bel, = struct.unpack('f', recv_data[18 + len_:])
            return rep
        elif request.cmd == 0x05:
            len_, = struct.unpack('!b', recv_data[2])
            rep.action.data, = recv_data[3:]
            return rep

    def face_srv_handler(self, request):
        print 'new face request arrived'
        rep = xm_FaceSrvResponse()
        recv_data = ''
        if request.cmd == 0x01:
            send_data = struct.pack('!bi', 0x01, len(request.req_name.data)) + request.req_name.data
        else:
            send_data = struct.pack('!b', 0x02)
        recv_data = self._send_wait(XM_winserver.WIN_IP, XM_winserver.FACE_PORT, send_data)
        print len(recv_data)
        status, = struct.unpack('!b', recv_data[0])
        print status
        if request.cmd == 0x01 and status == 0x00 : # no people in the frame
            rep.is_succ = False
            return rep
        if request.cmd == 0x01 and status == 0x01 :
            rep.is_succ = True
            return rep
        if request.cmd == 0x02 and status == 0x01 :#no person
            rep.rep_name.data = 'noperson'
            return rep
        if request.cmd == 0x02 and status == 0x02 :#recognized person
            rep.rep_name.data = recv_data[5: len(recv_data) - 4]
            print rep.rep_name
            rep.bel, = struct.unpack('f', recv_data[len(recv_data) - 4:])
            return rep
        if request.cmd == 0x02 and status == 0x03 :#stranger
            rep.rep_name.data = 'stranger'
            return rep

if __name__ == "__main__":
    rospy.init_node("xm_winserver")
    XM_winserver().start()

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
import time

log = core.getLogger()

PACKET_THRESHOLD = 10
TIME_WINDOW = 5

packet_history = {}
blocked_hosts = set()

class DynamicHostBlocker(object):
    def __init__(self, connection):
        self.connection = connection
        connection.addListeners(self)
        log.info("Dynamic Host Blocking active on switch %s", connection.dpid)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if not packet:
            return

        ip_pkt = packet.find('ipv4')

        if ip_pkt is not None:
            src_ip = str(ip_pkt.srcip)
            now = time.time()

            if src_ip not in packet_history:
                packet_history[src_ip] = []

            packet_history[src_ip] = [t for t in packet_history[src_ip] if now - t <= TIME_WINDOW]
            packet_history[src_ip].append(now)

            count = len(packet_history[src_ip])
            log.info("Host %s packet count in last %s sec = %s", src_ip, TIME_WINDOW, count)

            if src_ip in blocked_hosts:
                log.info("BLOCKED host %s -> dropping packet", src_ip)
                return

            if count >= PACKET_THRESHOLD:
                blocked_hosts.add(src_ip)
                log.info("THRESHOLD REACHED: Host %s BLOCKED", src_ip)
                return

        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.in_port = event.port
        msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
        self.connection.send(msg)

def launch():
    def start_switch(event):
        DynamicHostBlocker(event.connection)

    core.openflow.addListenerByName("ConnectionUp", start_switch)
    log.info("POX Dynamic Host Blocking controller started")

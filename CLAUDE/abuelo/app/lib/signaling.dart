import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:socket_io_client/socket_io_client.dart' as IO;

const String signalingServerUrl = 'https://abuelo-signal.onrender.com';

const Map<String, dynamic> iceServers = {
  'iceServers': [
    {'urls': 'stun:stun.l.google.com:19302'},
    {'urls': 'stun:stun1.l.google.com:19302'},
  ]
};

class Signaling {
  final String myRole;
  late IO.Socket _socket;
  RTCPeerConnection? _pc;
  MediaStream? _localStream;

  Function(MediaStream)? onLocalStream;
  Function(MediaStream)? onRemoteStream;
  Function()? onCallEnded;

  Signaling({required this.myRole});

  Future<void> connect() async {
    _localStream = await navigator.mediaDevices.getUserMedia({
      'audio': true,
      'video': {'facingMode': 'user'},
    });
    onLocalStream?.call(_localStream!);

    _socket = IO.io(signalingServerUrl, {
      'transports': ['websocket'],
      'autoConnect': false,
    });

    _socket.connect();

    _socket.onConnect((_) {
      _socket.emit('join', myRole);
    });

    _socket.on('offer', (data) async {
      await _createPeerConnection();
      await _pc!.setRemoteDescription(
        RTCSessionDescription(data['sdp'], data['type']),
      );
      final answer = await _pc!.createAnswer();
      await _pc!.setLocalDescription(answer);
      _socket.emit('answer', {'sdp': answer.sdp, 'type': answer.type});
    });

    _socket.on('answer', (data) async {
      await _pc!.setRemoteDescription(
        RTCSessionDescription(data['sdp'], data['type']),
      );
    });

    _socket.on('ice-candidate', (data) async {
      if (_pc != null) {
        await _pc!.addCandidate(RTCIceCandidate(
          data['candidate'],
          data['sdpMid'],
          data['sdpMLineIndex'],
        ));
      }
    });

    _socket.on('call-ended', (_) => onCallEnded?.call());
  }

  Future<void> _createPeerConnection() async {
    _pc = await createPeerConnection(iceServers);

    _localStream!.getTracks().forEach((track) {
      _pc!.addTrack(track, _localStream!);
    });

    _pc!.onIceCandidate = (candidate) {
      _socket.emit('ice-candidate', {
        'candidate': candidate.candidate,
        'sdpMid': candidate.sdpMid,
        'sdpMLineIndex': candidate.sdpMLineIndex,
      });
    };

    _pc!.onTrack = (event) {
      if (event.streams.isNotEmpty) {
        onRemoteStream?.call(event.streams[0]);
      }
    };
  }

  Future<void> call() async {
    await _createPeerConnection();
    final offer = await _pc!.createOffer();
    await _pc!.setLocalDescription(offer);
    _socket.emit('offer', {'sdp': offer.sdp, 'type': offer.type});
  }

  void hangup() {
    _socket.emit('hangup');
    _pc?.close();
    _localStream?.dispose();
    _socket.disconnect();
  }
}

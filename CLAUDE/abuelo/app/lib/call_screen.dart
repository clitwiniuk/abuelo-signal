import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'signaling.dart';

class CallScreen extends StatefulWidget {
  final String myRole;
  const CallScreen({super.key, required this.myRole});

  @override
  State<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends State<CallScreen> {
  final _localRenderer = RTCVideoRenderer();
  final _remoteRenderer = RTCVideoRenderer();
  late Signaling _signaling;
  bool _inCall = false;
  bool _waiting = false;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    await _localRenderer.initialize();
    await _remoteRenderer.initialize();

    _signaling = Signaling(myRole: widget.myRole);

    _signaling.onLocalStream = (stream) {
      setState(() => _localRenderer.srcObject = stream);
    };

    _signaling.onRemoteStream = (stream) {
      setState(() {
        _remoteRenderer.srcObject = stream;
        _inCall = true;
        _waiting = false;
      });
    };

    _signaling.onCallEnded = () {
      if (mounted) Navigator.pop(context);
    };

    await _signaling.connect();

    if (widget.myRole == 'padre') {
      setState(() => _waiting = true);
      await _signaling.call();
    }
  }

  @override
  void dispose() {
    _signaling.hangup();
    _localRenderer.dispose();
    _remoteRenderer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Video remoto (pantalla completa)
          if (_inCall)
            Positioned.fill(
              child: RTCVideoView(_remoteRenderer),
            ),

          // Pantalla de espera
          if (_waiting && !_inCall)
            const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(color: Colors.white),
                  SizedBox(height: 30),
                  Text(
                    'Llamando a Carlos...',
                    style: TextStyle(color: Colors.white, fontSize: 28),
                  ),
                ],
              ),
            ),

          // Video local (esquina)
          if (_inCall)
            Positioned(
              right: 16,
              top: 40,
              width: 100,
              height: 150,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: RTCVideoView(_localRenderer, mirror: true),
              ),
            ),

          // Botón colgar
          Positioned(
            bottom: 60,
            left: 0,
            right: 0,
            child: Center(
              child: GestureDetector(
                onTap: () {
                  _signaling.hangup();
                  Navigator.pop(context);
                },
                child: Container(
                  width: 90,
                  height: 90,
                  decoration: const BoxDecoration(
                    color: Colors.red,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.call_end, size: 50, color: Colors.white),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

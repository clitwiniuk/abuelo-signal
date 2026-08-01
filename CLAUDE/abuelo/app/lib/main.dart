import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'call_screen.dart';

void main() {
  runApp(const AbuApp());
}

class AbuApp extends StatelessWidget {
  const AbuApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Llamar a Carlos',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.green),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // En el móvil de tu padre pon: myRole = 'padre'
  // En tu móvil pon: myRole = 'carlos'
  static const String myRole = 'carlos';

  @override
  void initState() {
    super.initState();
    _requestPermissions();
  }

  Future<void> _requestPermissions() async {
    await [Permission.camera, Permission.microphone].request();
  }

  void _startCall() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CallScreen(myRole: myRole),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.account_circle, size: 120, color: Colors.green),
            const SizedBox(height: 30),
            const Text(
              'Carlos',
              style: TextStyle(fontSize: 40, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 60),
            GestureDetector(
              onTap: _startCall,
              child: Container(
                width: 200,
                height: 200,
                decoration: const BoxDecoration(
                  color: Colors.green,
                  shape: BoxShape.circle,
                ),
                child: const Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.videocam, size: 80, color: Colors.white),
                    SizedBox(height: 8),
                    Text(
                      'Llamar',
                      style: TextStyle(
                        fontSize: 28,
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

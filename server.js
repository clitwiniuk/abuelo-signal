const { createServer } = require('http');
const { Server } = require('socket.io');

const httpServer = createServer();
const io = new Server(httpServer, {
  cors: { origin: '*' }
});

const users = {};

io.on('connection', (socket) => {
  console.log('conectado:', socket.id);

  socket.on('join', (role) => {
    users[role] = socket.id;
    socket.data.role = role;
    console.log(`${role} conectado`);
  });

  socket.on('offer', (data) => {
    const targetId = users['carlos'];
    if (targetId) io.to(targetId).emit('offer', data);
  });

  socket.on('answer', (data) => {
    const targetId = users['padre'];
    if (targetId) io.to(targetId).emit('answer', data);
  });

  socket.on('ice-candidate', (data) => {
    const role = socket.data.role;
    const target = role === 'padre' ? 'carlos' : 'padre';
    const targetId = users[target];
    if (targetId) io.to(targetId).emit('ice-candidate', data);
  });

  socket.on('hangup', () => {
    const role = socket.data.role;
    const target = role === 'padre' ? 'carlos' : 'padre';
    const targetId = users[target];
    if (targetId) io.to(targetId).emit('call-ended');
  });

  socket.on('disconnect', () => {
    const role = socket.data.role;
    if (role) delete users[role];
    console.log(`${role} desconectado`);
  });
});

const PORT = process.env.PORT || 3000;
httpServer.listen(PORT, () => console.log(`servidor en puerto ${PORT}`));

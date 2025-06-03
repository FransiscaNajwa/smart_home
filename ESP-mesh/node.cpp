#include "painlessMesh.h"

#define MESH_PREFIX "myMesh"
#define MESH_PASSWORD "meshPassword"
#define MESH_PORT 5555

Scheduler userScheduler;
painlessMesh mesh;

void sendMessage();
Task taskSendMessage(TASK_SECOND * 5, TASK_FOREVER, &sendMessage);

void sendMessage() {
  static int counter = 0;
  String msg = "Message from Node " + String(mesh.getNodeId()) + ", count: " + String(counter++);
  mesh.sendBroadcast(msg);
  Serial.println("Sent: " + msg);
}

void setup() {
  Serial.begin(115200);
  mesh.setDebugMsgTypes(ERROR | STARTUP);
  mesh.init(MESH_PREFIX, MESH_PASSWORD, &userScheduler, MESH_PORT);
  userScheduler.addTask(taskSendMessage);
  taskSendMessage.enable();
}

void loop() {
  mesh.update();
}
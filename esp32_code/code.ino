#include <INST.h>
#include <SCS.h>
#include <SCSCL.h>
#include <SCSerial.h>
#include <SCServo.h>
#include <SMS_STS.h>

// the uart used to control servos.
// GPIO 18 - S_RXD, GPIO 19 - S_TXD, as default.
#define S_RXD 18
#define S_TXD 19
SMS_STS sms_sts;

#define VERBOSE true

void setup()
{

  // UART
  Serial1.begin(1000000, SERIAL_8N1, S_RXD, S_TXD);
  sms_sts.pSerial = &Serial1;
  while (!Serial1)
  {
  };

  // USB
  Serial.begin(115200);
}

void loop()
{
  // Check for serial input
  if (Serial.available() > 0)
  {
    String serialInput = Serial.readStringUntil('\n');

    // Process serial input and send response
    processSerialRequest(serialInput);
  }
}

// HANDLING COMMANDS

void processSerialRequest(String request)
{
  // Split the request by comma to extract command and parameters
  int commaIndex = request.indexOf(',');
  String command = request.substring(0, commaIndex);

  // Remove the command from the request string
  String parameters = request.substring(commaIndex + 1);

  // Trim any leading or trailing whitespace from parameters
  parameters.trim();

  // Process the command
  if (command == "CALIBRATE")
  {
    // Call the method to handle the 'CALIBRATE' command
    handleCalibrate(parameters);
  }
  else if (command == "MOVE")
  {
    // Call the method to handle the 'MOVE' command
    handleMove(parameters);
  }
  else if (command == "SYNC_MOVE")
  {
    // Call the method to handle the 'SYNC_MOVE' command
    handleSyncMove(parameters);
  }
  else if (command == "GET_POS")
  {
    // Call the method to handle the 'GET_POS' command
    handleGetPosition(parameters);
  }
  else if (command == "GET_TELEMETRY")
  {
    // Call the method to handle the 'GET_TELEMETRY' command
    handleGetTelemetry(parameters);
  }
  else
  {
    // Invalid command, send error response
      Serial.println("INVALID," + String(command));
  }
}

void handleCalibrate(String parameters)
{
  // Extract parameters
  int servoID = parameters.toInt();
  executeCalibrate(servoID);
}

void handleMove(String parameters)
{
  // Extract parameters
  int comma1 = parameters.indexOf(',');
  int comma2 = parameters.indexOf(',', comma1 + 1);
  int comma3 = parameters.indexOf(',', comma2 + 1);

  int servoID = parameters.substring(0, comma1).toInt();
  int position = parameters.substring(comma1 + 1, comma2).toInt();
  int speed = parameters.substring(comma2 + 1, comma3).toInt();
  int acc = parameters.substring(comma3 + 1).toInt();

  executeMove(servoID, position, speed, acc);
}

void handleSyncMove(String parameters)
{
  // Extract parameters
  int comma1 = parameters.indexOf(',');
  int comma2 = parameters.indexOf(',', comma1 + 1);
  int comma3 = parameters.indexOf(',', comma2 + 1);
  int comma4 = parameters.indexOf(',', comma3 + 1);

  u8 idn = parameters.substring(comma1 + 1, comma2).toInt();
  String servoIDsStr = parameters.substring(0, comma1);
  String positionsStr = parameters.substring(comma2 + 1, comma3);
  String speedsStr = parameters.substring(comma3 + 1, comma4);
  String accsStr = parameters.substring(comma4 + 1);

  // Convert String parameters to arrays
  u8 servoIDs[idn];
  s16 positions[idn];
  u16 speeds[idn];
  u8 accs[idn];

  // Parse comma-separated values and store them in arrays
  for (int i = 0; i < idn; i++)
  {
    int nextComma = servoIDsStr.indexOf(',');
    servoIDs[i] = servoIDsStr.substring(0, nextComma).toInt();
    servoIDsStr.remove(0, nextComma + 1);

    nextComma = positionsStr.indexOf(',');
    positions[i] = positionsStr.substring(0, nextComma).toInt();
    positionsStr.remove(0, nextComma + 1);

    nextComma = speedsStr.indexOf(',');
    speeds[i] = speedsStr.substring(0, nextComma).toInt();
    speedsStr.remove(0, nextComma + 1);

    nextComma = accsStr.indexOf(',');
    accs[i] = accsStr.substring(0, nextComma).toInt();
    accsStr.remove(0, nextComma + 1);
  }

  // Call executeSyncMove with the converted arrays
  executeSyncMove(servoIDs, idn, positions, speeds, accs);
}


void handleGetPosition(String parameters)
{
  // Extract parameters
  int servoID = parameters.toInt();
  executeGetPosition(servoID);
}

void handleGetTelemetry(String parameters)
{
  // Extract parameters
  int servoID = parameters.toInt();
  executeGetTelemetry(servoID);
}

// EXECUTING COMMANDS

void executeCalibrate(int servoID)
{
  sms_sts.CalibrationOfs(servoID);
}

void executeMove(int servoID, int position, int speed, int acc)
{
  sms_sts.WritePosEx(servoID, position, speed, acc);
}

void executeSyncMove(u8 servoIDs[], u8 IDN, s16 positions[], u16 speeds[], u8 accs[])
{
  sms_sts.SyncWritePosEx(servoIDs, IDN, positions, speeds, accs);
}

void executeGetPosition(int servoID)
{
  int position = sms_sts.ReadPos(servoID);
  Serial.println("POSITION, " + String(servoID) + ", " + String(position));
}

void executeGetTelemetry(int servoID)
{
  int Pos;
  int Speed;
  int Load;
  int Voltage;
  int Temp;
  int Move;
  int Current;

  Pos = sms_sts.ReadPos(servoID);
  Speed = sms_sts.ReadSpeed(servoID);
  Load = sms_sts.ReadLoad(servoID);
  Voltage = sms_sts.ReadVoltage(servoID);
  Temp = sms_sts.ReadTemper(servoID);
  Move = sms_sts.ReadMove(servoID);
  Current = sms_sts.ReadCurrent(servoID);

  Serial.println("TELEMETRY," + String(servoID) + ","+ String(Pos) + "," + String(Speed) + "," + String(Load) + ",V" + String(Voltage) + "," + String(Temp) + "," + String(Move) + "," + String(Current));
}
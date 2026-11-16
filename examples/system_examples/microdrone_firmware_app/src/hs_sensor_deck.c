/* HS microdrone sensor-deck integration: inert app-layer build proof.
 * Neither probes any physical deck nor writes motors/actuators.
 * The design revision is compiled into the real STM32 firmware build.
 * This does NOT implement BME688 or DS28E05 electronics/drivers.
 */
#include "app.h"
#include "FreeRTOS.h"
#include "task.h"
#define DEBUG_MODULE "HSDECK"
#include "debug.h"
#include "system_contract.h"

void appMain(void) {
  DEBUG_PRINT("HS microdrone design rev: %s; deck identity NOT VERIFIED\n",
              HS_SYSTEM_DESIGN_SHA256);
  for (;;) {
    vTaskDelay(M2T(5000));
  }
}

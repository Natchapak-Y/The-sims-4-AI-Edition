using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.AI;

[System.Serializable]
public class BrainResponse
{
    public string action;
    public string thought;
}

// 🌟 [ใหม่] โครงสร้างข้อมูลสำหรับกำหนดของที่ใช้งานได้ผ่าน Inspector
[System.Serializable]
public class InteractableConfig
{
    public string objectName;       // ชื่อเป้าหมาย เช่น Fridge, Bed
    public Transform objectTransform; // ตำแหน่งของวัตถุ
    public string affectedStat;     // ชื่อค่าพลังที่จะเปลี่ยน เช่น hunger, energy
    public float changeAmount;      // จำนวนที่เปลี่ยน เช่น -30 หรือ 30
    public float threshold;         // ขีดจำกัด เช่น 0 (หิวต่ำกว่า 0) หรือ 100 (พลังงานเกิน 100)
    public bool isThresholdUpper;   // ติ๊กถูก=เกินขีดจำกัดด้านบนถึงจะแจ้งเตือน / ไม่ติ๊ก=ต่ำกว่าขีดจำกัดด้านล่าง
    public string msgSuccess;       // ประโยคเมื่อทำสำเร็จพอดี
    public string msgExceedThreshold; // ประโยคเมื่อทำเกินขีดจำกัด
}

public class AIBrainConnection : MonoBehaviour
{
    [Header("Dynamic Body Stats (สถานะร่างกาย)")]
    // 🌟 [ใหม่] ใช้ Dictionary เพื่อให้เพิ่ม/ลดค่าพลังได้อิสระ ไม่จำกัดแค่ 3 ตัว
    private Dictionary<string, float> currentStats = new Dictionary<string, float>();

    [Header("Environment Objects (ตั้งค่าของที่ใช้ได้ตรงนี้!)")]
    public List<InteractableConfig> interactableObjects = new List<InteractableConfig>();

    [Header("Sensory Settings")]
    public float visionRadius = 15f; 
    public float horizontalFOV = 200f; 
    public float verticalFOV = 135f;   

    // 🌟 [ใหม่] คลังเก็บประโยค Feedback รวมไว้ที่เดียว แก้ไขง่าย
    private const string MSG_CANNOT_REACH = "I cannot reach {0}, it is too far away ({1:F1} meters).";
    private const string MSG_UNKNOWN_CMD = "My body cannot understand the command '{0}'. I must only use MoveDir, Approach, Interact, or Turn.";
    private const string MSG_INVALID_TARGET = "I cannot approach a vague concept like '{0}'. I must specify an exact object name from my Spatial Memory.";
    private const string MSG_FORGET_COORD = "I tried to approach '{0}' but I don't remember its coordinates.";

    private string apiUrl = "http://127.0.0.1:8000/think"; 
    private Coroutine currentActionCoroutine; 
    private NavMeshAgent agent; 
    private bool isBusy = false; 
    private string lastFeedback = ""; 

// 🌟 เปลี่ยนเป็น Dictionary เพื่อรับประกันว่า 1 ชื่อสิ่งของ จะมีแค่ 1 พิกัดเท่านั้น
    private Dictionary<string, Vector3> seenObjectsBuffer = new Dictionary<string, Vector3>();
    private float visionTimer = 0f;
    private float visionInterval = 0.05f; 

    void Start()
    {
        agent = GetComponent<NavMeshAgent>(); 
        
        // 🌟 ตั้งค่าเริ่มต้นให้ร่างกาย
        currentStats["energy"] = 50f;
        currentStats["hunger"] = 50f;
        currentStats["loneliness"] = 50f;

        Debug.Log("👁️ เริ่มระบบ Data-Driven AI Agent");
        StartCoroutine(AILoop());
    }

    void Update()
    {
        visionTimer += Time.deltaTime;
        if (visionTimer >= visionInterval)
        {
            ScanEnvironmentRealtime();
            visionTimer = 0f;
        }
    }    // 🌟 [เพิ่มฟังก์ชันนี้เข้าไปใหม่] ทำงานอัตโนมัติเมื่อกด Stop Game หรือทำลาย Object
    void OnDestroy()
    {
        // สั่งหยุด Coroutine ทั้งหมด (รวมถึง AILoop และ Action ต่างๆ)
        StopAllCoroutines();
        
        Debug.Log("🛑 ระบบ AI ถูกปิดอย่างปลอดภัย คืนหน่วยความจำเรียบร้อยแล้ว");
    }

    void ScanEnvironmentRealtime()
    {
        Collider[] hitColliders = Physics.OverlapSphere(transform.position, visionRadius);
        Vector3 eyePosition = transform.position + Vector3.up * 1.0f; 

        foreach (var hit in hitColliders)
        {
            string objName = hit.gameObject.name;
            if (objName == "AIAgent" || objName == "Plane" || objName.ToLower().Contains("wall")) continue;

            Vector3 closestSurfacePoint = hit.ClosestPoint(eyePosition);
            Vector3 directionToSurface = (closestSurfacePoint - eyePosition).normalized;

            Vector3 localDir = transform.InverseTransformDirection(directionToSurface);
            float hAngle = Mathf.Abs(Mathf.Atan2(localDir.x, localDir.z) * Mathf.Rad2Deg); 
            float vAngle = Mathf.Abs(Mathf.Asin(localDir.y) * Mathf.Rad2Deg);              

            if (hAngle <= horizontalFOV / 2f && vAngle <= verticalFOV / 2f)
            {
                float distanceToSurface = Vector3.Distance(eyePosition, closestSurfacePoint);
                if (Physics.Raycast(eyePosition, directionToSurface, out RaycastHit rayHit, distanceToSurface + 0.1f))
                {
                    if (rayHit.collider.gameObject == hit.gameObject)
                    {
                        // 🌟 [จุดที่ถูกแก้ไข] จับยัดลง Dictionary แทนการต่อ String
                        // ถ้าเจอสิ่งของชื่อเดิม (เช่น Fridge) มันจะอัปเดตพิกัด (rayHit.point) ให้เป็นค่าล่าสุดเสมอ 
                        // ทำให้ไม่มีรายชื่อ Fridge ซ้ำกันเป็นหางว่าวอีกต่อไป
                        seenObjectsBuffer[objName] = rayHit.point;
                        
                        Debug.DrawRay(eyePosition, directionToSurface * rayHit.distance, Color.red, 0.1f);
                    }
                }
            }
        }
    }

    IEnumerator AILoop()
    {
        while (true)
        {
            // 🌟 อัปเดตค่าพลังงาน (Clamp ไม่ให้เกินขอบเขต)
            currentStats["hunger"] = Mathf.Clamp(currentStats["hunger"] + 1f, -100f, 100f);
            currentStats["energy"] = Mathf.Clamp(currentStats["energy"] - 2f, -50f, 200f);
            currentStats["loneliness"] = Mathf.Clamp(currentStats["loneliness"] + 3f, -100f, 100f);

            if (!isBusy) 
            {
                // 🌟 [จุดที่ 3 ที่แก้ไขแล้ว] ดึงข้อมูลจาก Dictionary มาแปลงเป็น String
                List<string> seenList = new List<string>();
                foreach(var kvp in seenObjectsBuffer)
                {
                    // เอาชื่อ (Key) และ พิกัด (Value) มาต่อกันให้อยู่ในรูปแบบ "ชื่อ at (X: ..., Z: ...)"
                    seenList.Add($"\"{kvp.Key} at (X: {kvp.Value.x:F1}, Z: {kvp.Value.z:F1})\"");
                }
                string objects_nearbyJson = "[" + string.Join(",", seenList) + "]";
                seenObjectsBuffer.Clear();

                // 🌟 [แพ็คเกจ Stats ให้อยู่ในรูปแบบ Dynamic JSON] (ส่วนนี้เหมือนเดิม)
                List<string> statJsonList = new List<string>();
                foreach(var kvp in currentStats)
                {
                    // เปลี่ยน key ให้อยู่ในเครื่องหมายคำพูดคู่ (เช่น "hunger": 20)
                    statJsonList.Add($"\"{kvp.Key}\": {kvp.Value}");
                }
                string dynamicStatsJson = "{" + string.Join(", ", statJsonList) + "}";

                string jsonString = string.Format(System.Globalization.CultureInfo.InvariantCulture,
                    "{{" +
                    "\"stats\": {0}," +
                    "\"x\": {1}," +
                    "\"y\": {2}," +
                    "\"z\": {3}," +
                    "\"objects_nearby\": {4}," +
                    "\"last_feedback\": \"{5}\"" +
                    "}}", 
                    dynamicStatsJson, 
                    transform.position.x, transform.position.y, transform.position.z, 
                    objects_nearbyJson, lastFeedback.Replace("\"", "'").Replace("\n", " ")
                );

                using (UnityWebRequest www = new UnityWebRequest(apiUrl, "POST"))
                {
                    byte[] jsonToSend = new UTF8Encoding().GetBytes(jsonString);
                    www.uploadHandler = new UploadHandlerRaw(jsonToSend);
                    www.downloadHandler = new DownloadHandlerBuffer();
                    www.SetRequestHeader("Content-Type", "application/json");

                    yield return www.SendWebRequest();

                    if (www.result == UnityWebRequest.Result.Success)
                    {
                        string responseText = www.downloadHandler.text;
                        BrainResponse brainData = JsonUtility.FromJson<BrainResponse>(responseText);
                        Debug.Log($"💬 <color=cyan>AI คิดว่า: \"{brainData.thought}\"</color>");
                        
                        lastFeedback = ""; 
                        ExecuteAction(brainData.action);
                    }
                }
            }

            yield return new WaitForSeconds(5f); 
        }
    }

    void ExecuteAction(string response)
    {
        if (currentActionCoroutine != null) StopCoroutine(currentActionCoroutine);
        string r = response.ToLower(); 

        if (r.Contains("movedir")) 
        {
            float stepDistance = 3.0f; 
            try {
                string numStr = System.Text.RegularExpressions.Regex.Match(r, @"\d+(\.\d+)?").Value;
                if (!string.IsNullOrEmpty(numStr)) stepDistance = float.Parse(numStr);
            } catch { }

            Vector3 moveVector = transform.forward; 
            if (r.Contains("backward")) moveVector = -transform.forward;
            else if (r.Contains("left")) moveVector = -transform.right;
            else if (r.Contains("right")) moveVector = transform.right;

            Vector3 newDest = transform.position + (moveVector * stepDistance);
            currentActionCoroutine = StartCoroutine(WalkToTarget(newDest, $"MoveDir ({stepDistance} เมตร)"));
        }
        else if (r.Contains("interact"))
        {
            currentActionCoroutine = StartCoroutine(HandleInteraction(r));
        }
        else if (r.Contains("turn"))
        {
            float degrees = 90f; 
            string dir = "right"; 
            if (r.Contains("left")) dir = "left";
            try {
                string numStr = System.Text.RegularExpressions.Regex.Match(r, @"\d+(\.\d+)?").Value;
                if (!string.IsNullOrEmpty(numStr)) degrees = float.Parse(numStr);
            } catch { }

            currentActionCoroutine = StartCoroutine(TurnAgent(dir, degrees));
        }
        else if (r.Contains("approachpoint"))
        {
            try {
                var matches = System.Text.RegularExpressions.Regex.Matches(r, @"-?\d+(\.\d+)?");
                if (matches.Count >= 2)
                {
                    float targetX = float.Parse(matches[0].Value);
                    float targetZ = float.Parse(matches[1].Value);
                    Vector3 targetPos = new Vector3(targetX, transform.position.y, targetZ);
                    currentActionCoroutine = StartCoroutine(WalkToTarget(targetPos, "Approach"));
                }
                else lastFeedback = "Where is it?";
            } catch {
                lastFeedback = "I can't remember the location.";
            }
        }
        else if (r.Contains("approachunknown")) 
        {
            string target = "เป้าหมาย";
            var match = System.Text.RegularExpressions.Regex.Match(response, @"\((.+?)\)");
            if (match.Success) target = match.Groups[1].Value;
            lastFeedback = string.Format(MSG_FORGET_COORD, target);
        }
        else if (r.Contains("unknowncommand"))
        {
            string badCmd = "unknown";
            var match = System.Text.RegularExpressions.Regex.Match(response, @"\((.+?)\)");
            if (match.Success) badCmd = match.Groups[1].Value;
            lastFeedback = string.Format(MSG_UNKNOWN_CMD, badCmd);
        }
        else if (r.Contains("invalidtarget"))
        {
            string badTarget = "unknown";
            var match = System.Text.RegularExpressions.Regex.Match(response, @"\((.+?)\)");
            if (match.Success) badTarget = match.Groups[1].Value; 
            lastFeedback = string.Format(MSG_INVALID_TARGET, badTarget);
        }
        else 
        {
            lastFeedback = $"Body did not understand the command '{response}'.";
        }
    }

    // ==========================================
    // ⚙️ COROUTINES
    // ==========================================

    IEnumerator TurnAgent(string direction, float degrees)
    {
        isBusy = true;
        lastFeedback = "";
        float turnSpeed = 150f; 

        if (Mathf.Abs(degrees) >= 360f)
        {
            float totalRotation = 0f;
            while (totalRotation < 360f)
            {
                float step = turnSpeed * Time.deltaTime;
                transform.Rotate(0, (direction == "left" ? -step : step), 0);
                totalRotation += step;
                yield return null;
            }
            float snapAngle = Mathf.Round(transform.eulerAngles.y);
            transform.rotation = Quaternion.Euler(0, snapAngle, 0);
        }
        else
        {
            float targetAngle = (direction == "left") ? -degrees : degrees;
            Quaternion targetRotation = transform.rotation * Quaternion.Euler(0, targetAngle, 0);
            float angleDiff = Quaternion.Angle(transform.rotation, targetRotation);
            
            while (angleDiff > 1.0f)
            {
                transform.rotation = Quaternion.RotateTowards(transform.rotation, targetRotation, turnSpeed * Time.deltaTime);
                angleDiff = Quaternion.Angle(transform.rotation, targetRotation);
                yield return null;
            }
            transform.rotation = targetRotation; 
        }

        lastFeedback = $"Finished turning {direction} by {degrees} degrees.";
        isBusy = false;
    }

    IEnumerator HandleInteraction(string command)
    {
        isBusy = true; 
        yield return new WaitForSeconds(1.0f); 

        // 🌟 [ใหม่] ค้นหาว่าของที่ AI สั่ง Interact มีอยู่ใน Config ของเราหรือไม่
        InteractableConfig targetConfig = null;
        foreach (var config in interactableObjects)
        {
            if (command.Contains(config.objectName.ToLower()))
            {
                targetConfig = config;
                break;
            }
        }

        if (targetConfig != null && targetConfig.objectTransform != null)
        {
            float distance = float.MaxValue;
            Collider targetCollider = targetConfig.objectTransform.GetComponent<Collider>();
            
            if (targetCollider != null)
            {
                Vector3 surfacePoint = targetCollider.ClosestPoint(transform.position);
                distance = Vector3.Distance(transform.position, surfacePoint);
            }
            else
            {
                distance = Vector3.Distance(transform.position, targetConfig.objectTransform.position);
            }

            if (distance <= 3.0f) 
            {
                // 🌟 [จุดที่แก้] บังคับให้ชื่อ Stat ที่ตั้งใน Inspector กลายเป็นตัวพิมพ์เล็กทั้งหมด
                string statKey = targetConfig.affectedStat.ToLower(); 

                if (currentStats.ContainsKey(statKey))
                {
                    currentStats[statKey] += targetConfig.changeAmount;
                    float newVal = currentStats[statKey];

                    bool isThresholdBroken = targetConfig.isThresholdUpper ? (newVal > targetConfig.threshold) : (newVal < targetConfig.threshold);

                    if (isThresholdBroken)
                    {
                        lastFeedback = targetConfig.msgExceedThreshold;
                    }
                    else
                    {
                        lastFeedback = targetConfig.msgSuccess;
                    }
                }
                else
                {
                    lastFeedback = $"I used {targetConfig.objectName}, but nothing changed in my body.";
                }
            } 
            else 
            {
                lastFeedback = string.Format(MSG_CANNOT_REACH, targetConfig.objectName, distance);
            }
        }
        else 
        {
            lastFeedback = "I don't see that object nearby or cannot use it.";
        }

        isBusy = false; 
    }

    IEnumerator WalkToTarget(Vector3 targetPos, string actionType)
    {
        isBusy = true; 
        lastFeedback = ""; 

        NavMeshHit hit;
        if (NavMesh.SamplePosition(targetPos, out hit, 3.0f, NavMesh.AllAreas))
            agent.SetDestination(hit.position);
        else 
            agent.SetDestination(targetPos); 

        yield return new WaitUntil(() => !agent.pathPending);

        float timeout = 15f; 
        float timer = 0f;
        float successRadius = actionType.Contains("Approach") ? 1.5f : 0.5f;

        while (true) 
        {
            timer += Time.deltaTime; 
            Vector2 currentFlatPos = new Vector2(transform.position.x, transform.position.z);
            Vector2 targetFlatPos = new Vector2(targetPos.x, targetPos.z);
            float actualDistance = Vector2.Distance(currentFlatPos, targetFlatPos);

            if (actualDistance <= successRadius)
            {
                agent.ResetPath(); 
                if (actionType.Contains("Approach")) {
                    lastFeedback = $"{actionType} completed. I am now in front of the target and ready to Interact() if needed (Distance: {actualDistance:F1} m).";
                } else {
                    lastFeedback = $"{actionType} completed successfully.";
                }
                break;
            }

            if (timer > timeout)
            {
                agent.ResetPath();
                if (actualDistance <= 2.0f) {
                    lastFeedback = $"{actionType} completed successfully.";
                }
                else {
                    lastFeedback = $"I walked for too long and might be stuck. Current distance to target is ({actualDistance:F1} m).";
                }
                break; 
            }
            yield return null; 
        }
        isBusy = false; 
    }

    void OnDrawGizmos()
    {
        Gizmos.color = Color.yellow;
        Vector3 leftBoundary = Quaternion.Euler(0, -horizontalFOV / 2, 0) * transform.forward;
        Vector3 rightBoundary = Quaternion.Euler(0, horizontalFOV / 2, 0) * transform.forward;
        
        Gizmos.DrawRay(transform.position + Vector3.up, leftBoundary * visionRadius);
        Gizmos.DrawRay(transform.position + Vector3.up, rightBoundary * visionRadius);
        
        int segments = 20;
        float angleStep = horizontalFOV / segments;
        Vector3 previousPoint = transform.position + Vector3.up + leftBoundary * visionRadius;

        for (int i = 1; i <= segments; i++)
        {
            Vector3 dir = Quaternion.Euler(0, (-horizontalFOV / 2) + (angleStep * i), 0) * transform.forward;
            Vector3 nextPoint = transform.position + Vector3.up + dir * visionRadius;
            Gizmos.DrawLine(previousPoint, nextPoint);
            previousPoint = nextPoint;
        }
    }
}
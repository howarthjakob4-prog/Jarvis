package com.projectnova.jarvis

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.URL
import java.util.Locale
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity(), TextToSpeech.OnInitListener {
    private lateinit var endpointInput: EditText
    private lateinit var tokenInput: EditText
    private lateinit var macInput: EditText
    private lateinit var commandInput: EditText
    private lateinit var status: TextView
    private lateinit var tts: TextToSpeech
    private var recognizer: SpeechRecognizer? = null
    private var keepListening = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        tts = TextToSpeech(this, this)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 48, 32, 32)
        }
        val scroll = ScrollView(this).apply { addView(root) }
        setContentView(scroll)

        root.addView(TextView(this).apply {
            text = "JARVIS PHONE COMPANION"
            textSize = 26f
            gravity = Gravity.CENTER_HORIZONTAL
        })

        endpointInput = field("JARVIS URL, e.g. http://100.x.x.x:8765")
        tokenInput = field("Remote pairing token")
        macInput = field("PC MAC address, e.g. AA:BB:CC:DD:EE:FF")
        commandInput = field("Tell JARVIS what to do")
        root.addView(endpointInput)
        root.addView(tokenInput)
        root.addView(macInput)
        root.addView(commandInput)

        val wake = Button(this).apply {
            text = "Wake Computer"
            setOnClickListener { wakeComputerLocal() }
        }
        val send = Button(this).apply {
            text = "Send To JARVIS"
            setOnClickListener { sendCommand(commandInput.text.toString()) }
        }
        val voice = Button(this).apply {
            text = "Start Wake-Word Listening"
            setOnClickListener {
                keepListening = !keepListening
                text = if (keepListening) "Stop Wake-Word Listening" else "Start Wake-Word Listening"
                if (keepListening) startListening() else recognizer?.cancel()
            }
        }

        status = TextView(this).apply {
            text = "Ready. JARVIS can be reached over a private remote network; no public port-forwarding is required."
            textSize = 16f
            setPadding(0, 24, 0, 0)
        }

        root.addView(wake)
        root.addView(send)
        root.addView(voice)
        root.addView(status)

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), 7)
        }
    }

    private fun field(hintText: String) = EditText(this).apply {
        hint = hintText
        setSingleLine(true)
    }

    private fun wakeComputerLocal() {
        val mac = macInput.text.toString().trim()
        if (mac.isBlank()) {
            status.text = "Enter the computer's MAC address first."
            return
        }
        status.text = "Sending wake signal..."
        thread {
            try {
                val macBytes = mac.split(":", "-").map { it.toInt(16).toByte() }.toByteArray()
                require(macBytes.size == 6)
                val data = ByteArray(6 + 16 * 6)
                for (i in 0 until 6) data[i] = 0xFF.toByte()
                for (i in 6 until data.size) data[i] = macBytes[(i - 6) % 6]
                DatagramSocket().use { socket ->
                    socket.broadcast = true
                    socket.send(DatagramPacket(data, data.size, InetAddress.getByName("255.255.255.255"), 9))
                }
                runOnUiThread {
                    status.text = "Wake signal sent."
                    speak("Computer's turning on right now.")
                }
            } catch (e: Exception) {
                runOnUiThread { status.text = "Wake failed: ${e.message}" }
            }
        }
    }

    private fun sendCommand(text: String) {
        val endpoint = endpointInput.text.toString().trim().trimEnd('/')
        val token = tokenInput.text.toString().trim()
        val command = text.trim()
        if (endpoint.isBlank() || token.isBlank() || command.isBlank()) {
            status.text = "Enter the JARVIS URL, pairing token, and a command."
            return
        }
        status.text = "Contacting JARVIS..."
        thread {
            try {
                val conn = URL("$endpoint/api/send").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.setRequestProperty("Authorization", "Bearer $token")
                conn.doOutput = true
                conn.connectTimeout = 8000
                conn.readTimeout = 125000
                conn.outputStream.use { it.write(JSONObject().put("text", command).toString().toByteArray()) }
                val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
                val responseText = stream.bufferedReader().use { it.readText() }
                val obj = JSONObject(responseText)
                val reply = obj.optString("response", obj.optString("error", responseText))
                runOnUiThread {
                    status.text = reply
                    if (conn.responseCode in 200..299) speak(reply)
                }
            } catch (e: Exception) {
                runOnUiThread { status.text = "JARVIS connection error: ${e.message}" }
            }
        }
    }

    private fun startListening() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            keepListening = false
            status.text = "Speech recognition is not available on this phone."
            return
        }
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(this).also { sr ->
            sr.setRecognitionListener(object : RecognitionListener {
                override fun onResults(results: Bundle?) {
                    val heard = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                    status.text = if (heard.isBlank()) "Listening..." else "Heard: $heard"
                    val lower = heard.lowercase(Locale.US)
                    if (lower.contains("wake up jarvis")) wakeComputerLocal()
                    else if (lower.startsWith("jarvis ")) sendCommand(heard.substringAfter("jarvis "))
                    if (keepListening) startListening()
                }
                override fun onError(error: Int) { if (keepListening) status.postDelayed({ startListening() }, 700) }
                override fun onReadyForSpeech(params: Bundle?) { status.text = "Listening for 'Wake up Jarvis'..." }
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {}
                override fun onPartialResults(partialResults: Bundle?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        recognizer?.startListening(intent)
    }

    private fun speak(text: String) {
        if (text.isNotBlank()) tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "jarvis")
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) tts.language = Locale.US
    }

    override fun onDestroy() {
        keepListening = false
        recognizer?.destroy()
        tts.stop()
        tts.shutdown()
        super.onDestroy()
    }
}

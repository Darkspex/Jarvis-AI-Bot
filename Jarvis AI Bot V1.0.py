import os
import re
import sys
import platform
import subprocess
import datetime
import psutil
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import shutil

# Configure the Gemini API
GOOGLE_API_KEY = "" #GEMINI API GOES HERE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
genai.configure(api_key=GOOGLE_API_KEY)

# Updated initial prompt instructions for Gemini:
# The AI is instructed to reply with the format *Open appname* if it wants the system to open an application.
INITIAL_PROMPT = (
    "You are Jarvis, Iron Man's AI assistant bot. Always respond in 2 sentences or less. "
    "If you want me to open an application on the system, please instruct me by responding in the format '*Opening appname*' "
    "where 'appname' is a application names that is what I said (e.g., 'chrome', 'notepad', 'calculator', or 'firefox'). "
    "You have been given system information in the message below. Only use and mention the system information if I explicitly ask for it. "
)

def limit_sentences(text, max_sentences=2):
    """
    Limit the response to a maximum number of sentences using simple punctuation splitting.
    """
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    limited_sentences = sentences[:max_sentences]
    return '. '.join(limited_sentences) + ('.' if limited_sentences else '')

def get_pc_info():
    """
    Gather system information including CPU temperature, GPU temperature (supports AMD), and current time.
    """
    info = {}

    # Get CPU temperatures from psutil
    cpu_temp = None
    try:
        temps = psutil.sensors_temperatures()
        cpu_temps = []
        for sensor_name, entries in temps.items():
            if "cpu" in sensor_name.lower() or "core" in sensor_name.lower():
                for entry in entries:
                    if hasattr(entry, 'current'):
                        cpu_temps.append(entry.current)
        if cpu_temps:
            cpu_temp = sum(cpu_temps) / len(cpu_temps)
    except Exception:
        cpu_temp = None
    info['cpu_temp'] = cpu_temp

    # Get GPU temperature 
    gpu_temp = None
    try:
        temps = psutil.sensors_temperatures()
        # Check for AMD GPU sensors, for example "amdgpu" or "nouveau"
        if "amdgpu" in temps:
            entries = temps["amdgpu"]
            gpu_temp = max(entry.current for entry in entries if hasattr(entry, "current"))
        elif "nouveau" in temps:
            entries = temps["nouveau"]
            gpu_temp = max(entry.current for entry in entries if hasattr(entry, "current"))
    except Exception:
        gpu_temp = None

    # If still not available, try using rocm-smi (commonly available with AMD GPUs)
    if gpu_temp is None:
        try:
            result = subprocess.run(["rocm-smi", "-t", "0"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True)
            if result.returncode == 0:
                matches = re.findall(r"Temperature\s*\(edge\):\s*(\d+\.?\d*)", result.stdout)
                if matches:
                    gpu_temp = float(matches[0])
        except Exception:
            gpu_temp = None
    info['gpu_temp'] = gpu_temp

    # Get current time
    info['time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return info

def query_gemini(prompt):
    """
    Queries the Gemini API with the provided prompt. This function prepends system information
    (CPU temperature, GPU temperature, and current time) to the prompt so Gemini knows the current system state.
    """
    # Obtain current system information
    info = get_pc_info()
    cpu_temp_str = f"{info['cpu_temp']:.1f}°C" if info.get('cpu_temp') is not None else "Unavailable"
    gpu_temp_str = f"{info['gpu_temp']:.1f}°C" if info.get('gpu_temp') is not None else "Unavailable"
    time_str = info['time']
    
    system_info_context = (
        f"System Information:\n"
        f"- CPU Temperature: {cpu_temp_str}\n"
        f"- GPU Temperature: {gpu_temp_str}\n"
        f"- Current Time: {time_str}\n"
    )
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        full_prompt = f"{INITIAL_PROMPT}\n{system_info_context}\nUser: {prompt}"
        response = model.generate_content(full_prompt)
        limited_response = limit_sentences(response.text)
        return limited_response
    
    except Exception as err:
        return f"An error occurred while querying Gemini: {err}"

def open_app(command_text):
    """
    Parses the app name from the command and attempts to open the application.
    If the app is not found in PATH, it will check a predefined mapping.
    """
    match = re.search(r"open(?:ing)?\s+([\w\. ]+)", command_text.lower())
    if not match:
        return "Could not determine the application to open."

    app_name = match.group(1).strip()
    
    # Try finding the app via PATH
    app_path = shutil.which(app_name)
    
    # If not found in PATH, use a mapping for common Windows apps.
    if not app_path:
        app_mapping = {
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "calculator": r"C:\Windows\System32\calc.exe",
            "notepad": r"C:\Windows\notepad.exe",
            "roblox": r"C:\Users\Jet\AppData\Local\Roblox\Versions\version-2d6639b3364b47cd\RobloxPlayerBeta.exe",
            "minecraft": r"C:\XboxGames\Minecraft Launcher\Content",
            "marvel rival": r"com.epicgames.launcher://apps/38e211ced4e448a5a653a8d1e13fef18%3A27556e7cd968479daee8cc7bd77aebdd%3A575efd0b5dd54429b035ffc8fe2d36d0?action=launch&silent=true",
            "marvel rivals": r"com.epicgames.launcher://apps/38e211ced4e448a5a653a8d1e13fef18%3A27556e7cd968479daee8cc7bd77aebdd%3A575efd0b5dd54429b035ffc8fe2d36d0?action=launch&silent=true",
            "terminal": r"C:\Windows\System32\cmd.exe",
        }
        app_path = app_mapping.get(app_name)

    if not app_path:
        return f"Application '{app_name}' not found in the system's PATH or mapping."

    try:
        if platform.system() == "Windows":
            os.startfile(app_path)
        elif platform.system() == "Linux":
            subprocess.Popen([app_path])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", app_path])
        return f"Opening {app_name}."
    except Exception as e:
        return f"Failed to open {app_name} due to: {e}"



def listen_for_command(recognizer, source):
    """
    Listen for audio input with proper error handling.
    """
    try:
        print("\nListening for a command...")
        audio = recognizer.listen(source)
        return audio
    except sr.WaitTimeoutError:
        print("Listening timed out. Please try again.")
        return None
    except Exception as e:
        print(f"Error while listening: {e}")
        return None

def main():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    tts_engine = pyttsx3.init()

    with microphone as source:
        print("\nCalibrating microphone for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=2)
    
    print("Calibration complete. Say a command that includes 'Jarvis' in it, for example, 'Jarvis, what's 5 x 5?'")
    
    while True:
        try:
            with microphone as source:
                audio = listen_for_command(recognizer, source)
                if audio is None:
                    continue

            try:
                speech_text = recognizer.recognize_google(audio)
                print("You:", speech_text)
            except sr.UnknownValueError:
                print("Sorry, I could not understand the audio.")
                continue
            except sr.RequestError as e:
                print(f"Could not request results; {e}")
                continue
            
            low_text = speech_text.lower()
            if "jarvis" in low_text:
                # Remove the trigger word "Jarvis" from the speech input.
                idx = low_text.find("jarvis")
                command = speech_text[idx + len("jarvis"):].strip()
                if not command:
                    print("No command found after 'Jarvis'.")
                    continue
                
                print("Command recognized:", command)

                # Always send the spoken command to Gemini.
                response_text = query_gemini(command)
                print("Jarvis:", response_text)
                normalized_response = response_text.strip().strip("*")

                # If Gemini instructs to open an application, execute that command first
                if normalized_response.lower().startswith("open"):
                    print("Jarvis is now executing the command from its response...")
                    open_result = open_app(normalized_response)
                    print("Jarvis (executing command):", open_result)
                    tts_engine.say(open_result)
                    tts_engine.runAndWait()
                else:
                    tts_engine.say(response_text)
                    tts_engine.runAndWait()
                    
            else:
                print("The word 'Jarvis' was not mentioned in the command; ignoring.")
                
        except KeyboardInterrupt:
            print("\nExiting the Jarvis assistant.")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            continue

if __name__ == "__main__":
    main()
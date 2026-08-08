import os
import torch
import soundfile as sf
from chatterbox.tts import ChatterboxTTS

def run_test():
    print("Checking CUDA...")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. Chatterbox will run on CPU and be extremely slow.")
        
    print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
    
    print("Loading ChatterboxTTS model to CUDA...")
    model = ChatterboxTTS.from_pretrained(device="cuda")
    
    text = "Why is your Chrome still on the default new tab."
    print(f"Generating audio for: '{text}'")
    
    wav = model.generate(
        text,
        exaggeration=0.7,
        cfg_weight=0.5
    )
    
    output_path = "test_output.wav"
    sf.write(output_path, wav.squeeze().cpu().numpy(), model.sr)
    print(f"Done! Saved test audio to {output_path}")

if __name__ == "__main__":
    run_test()

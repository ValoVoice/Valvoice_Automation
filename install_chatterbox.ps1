# install_chatterbox.ps1

# Step 1: Remove existing torch to prevent conflicts
Write-Host "Uninstalling existing torch..."
.\venv\Scripts\python.exe -m pip uninstall torch torchvision torchaudio -y

# Step 2: Install CUDA 12.8 build for RTX 5060 (Blackwell/sm_120)
Write-Host "Installing Torch cu128 for RTX 5060 compatibility..."
.\venv\Scripts\python.exe -m pip install torch==2.9.1+cu128 torchaudio==2.9.1+cu128 --index-url https://download.pytorch.org/whl/cu128

# Step 3: Install chatterbox WITHOUT its broken torch pin
Write-Host "Installing chatterbox-tts with --no-deps..."
.\venv\Scripts\python.exe -m pip install chatterbox-tts --no-deps

# Step 4: Install the FULL dependency list manually
Write-Host "Installing Chatterbox dependencies..."
.\venv\Scripts\python.exe -m pip install numpy scipy soundfile tokenizers conformer einops encodec s3tokenizer resemble-perth pyyaml safetensors huggingface_hub transformers

# Step 5: Verify CUDA
Write-Host "Verifying CUDA availability..."
.\venv\Scripts\python.exe -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')"

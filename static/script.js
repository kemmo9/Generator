document.getElementById('video-form').addEventListener('submit', async function(event) {
    event.preventDefault();

    const script = document.getElementById('script').value;
    const generateBtn = document.getElementById('generate-btn');
    const statusArea = document.getElementById('status-area');

    if (!script) {
        alert('Please enter a script.');
        return;
    }

    // Disable button and show loading status
    generateBtn.disabled = true;
    generateBtn.textContent = 'Generating... Please Wait';
    statusArea.textContent = 'Sending request... This can take up to a minute.';

    try {
        const response = await fetch('/api/generate-video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ script: script }),
        });

        if (response.ok) {
            statusArea.textContent = 'Video generated! Starting download...';
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'ai_generated_video.mp4';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            statusArea.textContent = 'Download started successfully!';
        } else {
            const error = await response.json();
            statusArea.textContent = `Error: ${error.detail || 'Failed to generate video.'}`;
        }
    } catch (error) {
        statusArea.textContent = 'An unexpected error occurred. Please check the console.';
        console.error('Fetch error:', error);
    } finally {
        // Re-enable button
        generateBtn.disabled = false;
        generateBtn.textContent = 'Generate Video';
    }
});
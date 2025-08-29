import os
import json
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class EventExtractor:
    def __init__(self):
        """
        Initialize the EventExtractor with Gemini API key from environment variables
        """
        self.api_key = os.getenv('API_KEY')
        if not self.api_key:
            raise ValueError("API_KEY not found in environment variables. Please check your .env file.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def extract_event_info(self, image_path):
        """
        Extract event information from an image using Gemini API
        
        Args:
            image_path (str): Path to the image file
            
        Returns:
            dict: Extracted event information
        """
        try:
            # Load and process the image
            image = Image.open(image_path)
            
            # Create a detailed prompt for event information extraction
            prompt = """
            Analyze this image carefully and extract the following event information:
            
            1. Event Name: The title or name of the event
            2. Location: The venue, address, or place where the event will be held
            3. Date: The date when the event will occur (format as YYYY-MM-DD if possible)
            4. Time: The time when the event starts/ends (format as HH:MM AM/PM if possible)
            
            Please provide the response in the following JSON format:
            {
                "event_name": "extracted event name or null if not found",
                "location": "extracted location or null if not found", 
                "date": "extracted date in YYYY-MM-DD format or original format if can't convert or null if not found",
                "time": "extracted time or null if not found",
                "confidence": "high/medium/low based on clarity of information",
                "additional_info": "any other relevant details found"
            }
            
            If any information is not clearly visible or available, set the value to null.
            Be as accurate as possible and only extract information that is clearly visible in the image.
            """
            
            # Generate content using Gemini
            response = self.model.generate_content([prompt, image])
            
            # Parse the JSON response
            try:
                # Extract JSON from response text
                response_text = response.text.strip()
                if response_text.startswith('```json'):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith('```'):
                    response_text = response_text[3:-3].strip()
                
                event_info = json.loads(response_text)
                
                # Add metadata
                event_info['extracted_at'] = datetime.now().isoformat()
                event_info['source_image'] = os.path.basename(image_path)
                
                # Display results instead of saving
                self._display_results(event_info)
                
                return event_info
                
            except json.JSONDecodeError:
                # If JSON parsing fails, return raw response
                return {
                    "event_name": None,
                    "location": None,
                    "date": None,
                    "time": None,
                    "confidence": "low",
                    "additional_info": response.text,
                    "error": "Failed to parse JSON response",
                    "extracted_at": datetime.now().isoformat(),
                    "source_image": os.path.basename(image_path)
                }
                
        except Exception as e:
            return {
                "event_name": None,
                "location": None,
                "date": None,
                "time": None,
                "confidence": "low",
                "additional_info": None,
                "error": f"Error processing image: {str(e)}",
                "extracted_at": datetime.now().isoformat(),
                "source_image": os.path.basename(image_path) if os.path.exists(image_path) else "unknown"
            }
    
    def _display_results(self, result):
        """
        Display extracted event information in a formatted way
        
        Args:
            result (dict): Extracted event information
        """
        print("\n" + "="*50)
        print("EXTRACTED EVENT INFORMATION")
        print("="*50)
        print(f"Source: {result.get('source_image', 'Unknown')}")
        print(f"Event Name: {result.get('event_name', 'Not found')}")
        print(f"Location: {result.get('location', 'Not found')}")
        print(f"Date: {result.get('date', 'Not found')}")
        print(f"Time: {result.get('time', 'Not found')}")
        print(f"Confidence: {result.get('confidence', 'Unknown')}")
        
        if result.get('additional_info'):
            print(f"Additional Info: {result.get('additional_info')}")
        
        if result.get('error'):
            print(f"Error: {result.get('error')}")
            
        print(f"Extracted at: {result.get('extracted_at', 'Unknown')}")
        print("="*50)
    
    def process_multiple_images(self, image_paths):
        """
        Process multiple images and extract event information from each
        
        Args:
            image_paths (list): List of image file paths
            
        Returns:
            list: List of extracted event information dictionaries
        """
        results = []
        for image_path in image_paths:
            print(f"Processing: {image_path}")
            result = self.extract_event_info(image_path)
            results.append(result)
            print(f"✓ Completed: {os.path.basename(image_path)}")
        
        return results
    
    def save_results(self, results, output_file="extracted_events.json"):
        """
        Save extracted results to a JSON file (optional - for backup purposes)
        
        Args:
            results (list or dict): Extracted event information
            output_file (str): Output file path
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results saved to: {output_file}")

def main():
    """Main function to run the event extractor"""
    parser = argparse.ArgumentParser(description='Extract event information from images using Gemini API')
    parser.add_argument('images', nargs='+', help='Path(s) to image file(s)')
    parser.add_argument('--save', action='store_true', help='Save results to JSON file')
    parser.add_argument('--output', '-o', default='extracted_events.json', help='Output JSON file path (only used with --save)')
    
    args = parser.parse_args()
    
    # Initialize the extractor (API key loaded from .env)
    try:
        extractor = EventExtractor()
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    # Process images
    if len(args.images) == 1:
        # Single image
        result = extractor.extract_event_info(args.images[0])
        
        # Optionally save results
        if args.save:
            extractor.save_results(result, args.output)
    else:
        # Multiple images
        results = extractor.process_multiple_images(args.images)
        
        # Optionally save results
        if args.save:
            extractor.save_results(results, args.output)

# Example usage function for interactive use
def interactive_example():
    """
    Interactive example for testing the script
    """
    print("Event Information Extractor")
    print("="*30)
    
    # Initialize extractor (API key from .env)
    try:
        extractor = EventExtractor()
        print("✓ API key loaded from .env file")
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    # Get image path
    image_path = input("Enter the path to your image file: ").strip()
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return
    
    # Process image
    print(f"\nProcessing {image_path}...")
    result = extractor.extract_event_info(image_path)
    
    # Ask if user wants to save
    save_choice = input("\nWould you like to save these results to a JSON file? (y/n): ").strip().lower()
    if save_choice in ['y', 'yes']:
        output_file = f"event_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        extractor.save_results(result, output_file)

if __name__ == "__main__":
    # Check if running with command line arguments
    import sys
    if len(sys.argv) > 1:
        main()
    else:
        # Run interactive mode
        interactive_example()
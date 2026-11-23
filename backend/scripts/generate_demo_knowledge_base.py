"""
Generate 14 comprehensive, clearly-labeled synthetic demonstration documents in pdf/
for the Real Estate AI Chatbot CTO/Client Demo.
Each document contains realistic specifications and clear demonstration labels.
"""

import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("fitz (PyMuPDF) is required to generate PDFs.")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PDF_DIR = PROJECT_ROOT / "pdf"
PDF_DIR.mkdir(parents=True, exist_ok=True)

DOCUMENTS = [
    {
        "filename": "Casagrand_Aquagrove_1BHK_Studio_Specifications.pdf",
        "title": "Casagrand Aquagrove - 1BHK & Studio Apartment Model Specifications",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Unit Overview & Configuration:", [
                "Configuration: 1BHK Studio Smart Suite",
                "Super Built-up Area: 620 sq ft (Carpet Area: 445 sq ft)",
                "Living & Dining Area: 10' x 16' with private Juliet balcony",
                "Master Bedroom: 10' x 12' with built-in wardrobe alcove",
                "Kitchenette: 7' x 8' with stainless steel sink & granite counter",
                "Bathroom: 5' x 8' with wall-hung EWC and glass shower partition",
                "Ceiling Height: 10' 0\" clear height",
            ]),
            ("Finishes & Flooring:", [
                "Living, Bedroom & Kitchen Flooring: Vitrified tiles 2' x 2' (Simpolo / Somany)",
                "Bathroom Flooring: Anti-skid ceramic tiles 1' x 1' with matte finish",
                "Wall Tile Dado: Designer ceramic tiles up to 7' height in bathroom",
                "Interior Painting: 2 coats acrylic putty + 1 coat primer + 2 coats Asian Paints Royale",
            ]),
            ("Electrical & Plumbing:", [
                "Switches & Sockets: Anchor Roma modular switches",
                "Wiring: Finolex FRLS concealed copper wiring",
                "Air Conditioning: Split AC copper piping provision in bedroom and living room",
                "Power Backup: 1.0 KVA dedicated DG power backup per unit",
            ]),
        ],
    },
    {
        "filename": "Casagrand_Aquagrove_4BHK_Penthouse_Luxury_Specifications.pdf",
        "title": "Casagrand Aquagrove - 4BHK Penthouse Sky Villa Specifications",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Penthouse Overview & Dimensions:", [
                "Configuration: 4BHK + 4T + Powder Room + Maid Room + Private Terrace",
                "Super Built-up Area: 3,450 sq ft (Carpet Area: 2,680 sq ft)",
                "Grand Living & Dining: 18' x 32' with double-height ceiling (20 feet)",
                "Master Bedroom Suite: 16' x 20' with walk-in wardrobe (8' x 10') and private deck (10' x 18')",
                "Bedroom 2: 14' x 15' with attached bathroom (6' x 9')",
                "Bedroom 3: 13' x 14' with attached bathroom (6' x 8')",
                "Bedroom 4 / Home Cinema Lounge: 12' x 16' with acoustic wall insulation",
                "Maid Room with Toilet: 7' x 8' separate service entrance",
            ]),
            ("Premium Flooring & Wall Finishes:", [
                "Living, Dining & Foyer: Imported Italian Botticino marble flooring with mirror polish",
                "Master Bedroom Flooring: Premium engineered oak hardwood flooring",
                "Other Bedrooms: 4' x 2' glazed vitrified tiles with book-matched veins",
                "Bathrooms: Full-body porcelain slab tiles up to false ceiling height",
            ]),
            ("Smart Home & Luxury Fittings:", [
                "Sanitaryware: Duravit wall-hung EWCs with concealed Geberit dual flush cisterns",
                "CP Fittings: Grohe thermostatic shower mixers and waterfall spout in master bath",
                "Home Automation: Legrand Arteor smart touch switches and app-controlled lighting",
                "Private Deck: Jacuzzi whirlpool tub provision on open sky terrace",
            ]),
        ],
    },
    {
        "filename": "Casagrand_Aquagrove_Villa_Independent_Living_Guide.pdf",
        "title": "Casagrand Aquagrove - Gated Coastal Villa Independent Living Guide",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Villa Architecture & Land Allocation:", [
                "Configuration: 3BHK and 4BHK Independent G+1 Coastal Villas",
                "Plot Land Area: 2,400 sq ft; Built-up Area: 1,890 sq ft to 2,350 sq ft",
                "Private Garden: 450 sq ft landscaped garden with automatic drip irrigation",
                "Car Port: Covered parking pergola for 2 luxury SUVs with 32A EV charger socket",
                "Rooftop Terrace: 650 sq ft private terrace with pergola and solar inverter provision",
            ]),
            ("Independent Water & Power Infrastructure:", [
                "Individual Underground Water Sump: 6,000 Litres RCC sump per villa",
                "Overhead Water Tank: 2,000 Litres multi-layer antibacterial tank",
                "Solar Water Heater: 200 Litres rooftop solar water heating system",
                "100% Dedicated DG Power Backup: 3.5 KVA generator supply per villa",
            ]),
            ("Privacy & Security Architecture:", [
                "Compound Wall: 5' 0\" solid block compound wall with decorative MS gate",
                "Security: Yale Biometric video door phone and dual IR perimeter motion sensors",
                "Pet Freedom: Private fenced lawn allows unrestricted domestic pet movement",
            ]),
        ],
    },
    {
        "filename": "Structural_Design_and_Civil_Specifications_Handbook.pdf",
        "title": "Casagrand Aquagrove - Structural Design & Civil Specifications Handbook",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Seismic & Structural Foundation:", [
                "Seismic Compliance: Designed strictly in accordance with IS 1893 (Seismic Zone III) and IS 456",
                "Foundation: Deep pile foundation drilled into solid bedrock with raft pile caps",
                "Structural Framing: RCC framed structure engineered for earthquake resistance",
                "Steel Reinforcement: High-yield Fe 550D TMT corrosion-resistant steel bars (Tata Tiscon / JSW)",
                "Concrete Grade: Ready Mix Concrete M30 & M35 grade with computerized batching quality control",
            ]),
            ("Masonry & Wall Construction:", [
                "External Walls: 200mm thick Autoclaved Aerated Concrete (AAC) blocks for thermal and acoustic insulation",
                "Internal Partition Walls: 100mm thick solid concrete blocks with fiber mesh plaster joint reinforcement",
                "Floor-to-Ceiling Clear Height: 10' 0\" in standard apartments; 11' 0\" in penthouses and villas",
            ]),
            ("Waterproofing & Anti-Termite Treatment:", [
                "Foundation Anti-Termite: Comprehensive chemical barrier soil treatment as per IS 6313 (Part II)",
                "Wet Area Waterproofing: 3-layer elastomeric polyurethane waterproofing membrane with 10-year warranty",
                "Terrace Waterproofing: High-albedo reflective thermal insulation screed over waterproof membrane",
            ]),
        ],
    },
    {
        "filename": "Doors_Windows_and_Hardware_Schedule.pdf",
        "title": "Casagrand Aquagrove - Doors, Windows & Hardware Schedule",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Main Entrance Door:", [
                "Door Frame: First-class African Teak wood frame measuring 8' 0\" height x 4' 0\" width",
                "Door Shutter: 40mm thick solid core flush shutter with natural teak veneer on both sides",
                "Smart Lock: Yale biometric digital lock (Fingerprint recognition, PIN code, RFID card, physical key override)",
                "Hardware: Heavy-duty stainless steel ball-bearing hinges, magnetic door stopper, and wide-angle optical viewer",
            ]),
            ("Internal Bedroom & Toilet Doors:", [
                "Bedroom Doors: Hardwood frame with 35mm thick modular laminated flush doors and Godrej mortise locks",
                "Toilet Doors: Water-resistant FRP / WPC coated shutter with cylindrical privacy lockset",
                "Balcony Doors: UPVC heavy-duty sliding french doors with toughened safety glass and multi-point lock",
            ]),
            ("Windows & Glazing:", [
                "Window Frames: Premium 3-track UPVC sliding window system (Kommerling / Fenesta)",
                "Glass Specification: 6mm thick Saint-Gobain clear float toughened glass",
                "Bug Mesh: Stainless steel high-transparency mosquito screen track included on all operable windows",
                "Ventilators: UPVC top-hung ventilators with exhaust fan cutout and obscure pinhead privacy glass",
            ]),
        ],
    },
    {
        "filename": "Flooring_Wall_Finishes_and_Painting_Schedule.pdf",
        "title": "Casagrand Aquagrove - Flooring, Wall Finishes & Painting Schedule",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Flooring Schedule by Area:", [
                "Foyer, Living & Dining: 4' x 2' (1200mm x 600mm) glazed vitrified tiles with nano-polish (Kajaria / Somany)",
                "Master Bedroom: 4' x 2' wooden-finish vitrified tiles for warm aesthetic",
                "Other Bedrooms: 2' x 2' (600mm x 600mm) double-charged vitrified tiles",
                "Bathrooms: 1' x 1' anti-skid ceramic floor tiles and matching 2' x 1' glazed ceramic wall tiles up to false ceiling (7')",
                "Balconies & Utility: Matte finish rustic anti-skid ceramic tiles (300mm x 300mm)",
                "Common Corridors & Lift Lobbies: Combination of polished granite slabs and vitrified tile borders",
            ]),
            ("Painting & Surface Preparation:", [
                "Internal Walls: 2 coats of water-resistant acrylic putty, 1 coat of acrylic primer, 2 coats of Asian Paints Royale Luxury Emulsion",
                "Ceiling Painting: 2 coats of acrylic putty and 2 coats of Asian Paints tractor emulsion in bright white",
                "Exterior Walls: 1 coat of exterior primer followed by 2 coats of Asian Paints Apex Ultima weather-proof acrylic emulsion with silicone protection",
                "Metal Railings: 1 coat of red oxide primer followed by 2 coats of synthetic enamel paint (Satin Black)",
            ]),
        ],
    },
    {
        "filename": "Electrical_Plumbing_and_HVAC_Schedule.pdf",
        "title": "Casagrand Aquagrove - Electrical, Plumbing & HVAC Schedule",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Electrical Wiring & Switchgear:", [
                "Concealed Conduit: Heavy-duty rigid PVC conduits embedded in RCC slabs and walls",
                "Wires: 100% electrolytic copper conductor FRLS insulated wires (Finolex / Polycab)",
                "Modular Switches: Schneider Electric / Legrand modular switches with silver cadmium contacts",
                "Distribution Board: Miniature Circuit Breaker (MCB) and Earth Leakage Circuit Breaker (ELCB) for human shock protection",
                "Air Conditioner Points: Dedicated 20A power points and pre-installed drain pipes in all bedrooms and living hall",
                "Generator Power Backup: 100% backup for all elevators, pumps, street lighting; 1.5 KVA per 2BHK/3BHK unit",
            ]),
            ("Plumbing, Water Lines & Fixtures:", [
                "Water Supply Piping: Astral / Ashirvad CPVC pipes for domestic hot and cold water lines",
                "Drainage & Soil Piping: Heavy-duty PVC pipes connected to centralized Sewage Treatment Plant (STP)",
                "Sanitaryware: Kohler / Grohe wall-hung European Water Closets (EWC) with concealed pneumatic dual-flush tank",
                "CP Fittings: Grohe brass chrome-plated single-lever hot/cold basin mixers and thermostatic overhead shower",
                "Water Meter: Individual ultrasonic smart digital water meter for each apartment",
            ]),
        ],
    },
    {
        "filename": "Clubhouse_Sports_and_Recreation_Amenities_Directory.pdf",
        "title": "Casagrand Aquagrove - Clubhouse & Sports Amenities Directory",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Grand 25,000 Sq Ft Central Clubhouse:", [
                "Building Profile: G+2 contemporary clubhouse with double-height reception lobby and guest suites",
                "Swimming Pool: Half-Olympic (25m x 12.5m) temperature-controlled outdoor pool with dedicated shallow kids' pool",
                "Pool Deck: Wooden finish deck with poolside loungers, sun umbrellas, and changing pavilions",
                "Gymnasium: 3,500 sq ft fitness hub fitted with Technogym treadmills, cross trainers, free weights, and smith machines",
                "Yoga & Aerobics Studio: Sprung hardwood floor with mirror wall and surround sound audio system",
            ]),
            ("Indoor & Outdoor Sports Courts:", [
                "Badminton: 2 BWF-standard wooden indoor badminton courts with LED court lighting",
                "Squash Court: 1 glass-backed competition squash court with timber flooring",
                "Tennis: 1 floodlit synthetic turf tennis court on the podium level",
                "Basketball: 1 multipurpose half-court for basketball and futsal",
                "Jogging Track: 1.2 km continuous rubberized fitness loop encircling the central landscaped park",
                "Indoor Games Arena: Billiards room with 2 championship tables, table tennis room, carrom, and chess tables",
            ]),
        ],
    },
    {
        "filename": "Security_Access_Control_and_Smart_Home_Guidelines.pdf",
        "title": "Casagrand Aquagrove - Security, Access Control & Smart Home Guidelines",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("3-Tier Physical & Electronic Security:", [
                "Perimeter Security: 8-foot boundary wall equipped with solar-powered infrared perimeter intrusion detection beams",
                "Main Entry Gate: 24/7 security control post with automated RFID vehicle boom barriers and tire killers",
                "CCTV Surveillance: Network of 180+ Full HD 4K night-vision IP cameras with 30-day cloud recording",
                "Tower Lobby Security: Biometric fingerprint and access card readers at every ground-level entrance lobby",
            ]),
            ("Smart Visitor Management & In-Home Tech:", [
                "MyGate Integration: Digital visitor authorization and delivery pass generation via resident mobile application",
                "Video Door Phone: 7-inch color video intercom screen connected to tower gate and visitor lobby",
                "Gas Leak Detection: Automated smart LPG gas leakage sensor with automatic shut-off solenoid valve",
                "Fire Safety: Heat and smoke detectors in every apartment linked to central fire management panel",
            ]),
        ],
    },
    {
        "filename": "Parking_Allocation_EV_Charging_and_Traffic_Rules.pdf",
        "title": "Casagrand Aquagrove - Parking Allocation & EV Charging Policy",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Parking Allocation Matrix:", [
                "1BHK / Studio: 1 reserved covered two-wheeler parking slot",
                "2BHK Units: 1 reserved covered car parking slot in Basement 1 or Basement 2",
                "3BHK & 4BHK Units: 2 reserved covered car parking slots (tandem or side-by-side depending on unit)",
                "Visitor Parking: 45 designated surface visitor car parking bays with 4-hour parking limit",
            ]),
            ("Electric Vehicle (EV) Infrastructure:", [
                "EV Charging Points: Dedicated 15A / 7.4 kW AC single-phase EV charging socket at every allotted resident slot",
                "Common Fast Charger: 2 DC fast-charging stations (30 kW) located near visitor bay for rapid top-ups",
                "Billing: Smart prepaid sub-meter tied to resident electricity app account",
            ]),
            ("Traffic Circulation & Speed Rules:", [
                "Speed Limit: Maximum 15 km/h strictly enforced across all basements, ramps, and internal driveways",
                "Pedestrian Safety: Ground level is 100% vehicle-free in central podium zones for child safety",
            ]),
        ],
    },
    {
        "filename": "Water_Management_STP_and_Rainwater_Harvesting_Policy.pdf",
        "title": "Casagrand Aquagrove - Water Management & Environmental Sustainability Policy",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Water Supply & Dual Plumbing System:", [
                "Water Sources: Municipal drinking water connection backed up by 4 borewells and deep groundwater recharge",
                "Water Treatment Plant (WTP): On-site automated multimedia sand filter and activated carbon filter plant",
                "Dual Plumbing: Fresh treated water supplied for drinking and bathing; recycled STP water supplied for flushing",
                "Water Softener: Centralized ion-exchange water softening plant ensuring water hardness below 120 ppm",
            ]),
            ("Sewage Treatment & Greywater Recycling:", [
                "STP Technology: Sequencing Batch Reactor (SBR) advanced technology plant with 350 KLD capacity",
                "Odorless Treatment: Underground tertiary treatment including ultrafiltration and ozonation for 100% odorless water",
                "Recycled Water Use: 100% of treated water utilized for landscape drip irrigation and toilet flushing",
            ]),
            ("Rainwater Harvesting & Green Credentials:", [
                "Percolation Pits: 24 recharge wells located across the periphery connected to catchments",
                "Retention Reservoir: 100,000 Litres underground stormwater storage tank for rainwater harvesting",
                "Green Rating: IGBC Green Homes Pre-Certified Gold Rating compliance",
            ]),
        ],
    },
    {
        "filename": "Payment_Schedules_Possession_Timelines_and_Handover_Policy.pdf",
        "title": "Casagrand Aquagrove - Payment Schedule & Handover Policy",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Construction-Linked Payment Schedule:", [
                "Booking Advance: 10% on initial property booking confirmation",
                "Agreement Signing: 15% upon execution of Agreement for Sale within 30 days",
                "Foundation Completion: 10% upon completion of foundation and piling works",
                "Basement Slabs: 10% upon casting of basement floor roof slab",
                "Superstructure Milestones: 5% per floor slab completion (Floors 1 to 18)",
                "Brickwork & Plastering: 10% upon completion of unit internal plastering",
                "Flooring & Tiling: 10% upon completion of unit vitrified tiling",
                "Handover & Possession: 5% balance upon issuance of Occupancy Certificate and key handover",
            ]),
            ("RERA & Statutory Registration:", [
                "RERA Registration Number: TNRERA/PRJ/2024/00142",
                "Completion Timeline: Phase 1 Handover: December 2026; Phase 2 Handover: September 2027",
                "Defect Liability Period: 5-year builder structural and construction warranty as per RERA section 14(3)",
            ]),
            ("Handover Inspection & Snagging Protocol:", [
                "Pre-Delivery Inspection (PDI): 30-day advance snagging walkthrough with customer relationship manager",
                "Rectification Window: 14 days to resolve any minor paint, cosmetic, or fixture adjustments prior to key handover",
            ]),
        ],
    },
    {
        "filename": "Home_Renovation_Interior_Work_and_Architectural_Guidelines.pdf",
        "title": "Casagrand Aquagrove - Interior Renovation & Architectural Guidelines",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Working Hours & Noise Regulations:", [
                "Permitted Working Days: Monday to Saturday only",
                "Working Hours: 9:00 AM to 6:00 PM (Noisy drilling or cutting permitted strictly between 10:00 AM and 4:00 PM)",
                "Prohibited Days: Strictly no interior modification, carpentry, or drilling on Sundays and National Holidays",
            ]),
            ("Structural Alterations & Safety Rules:", [
                "Prohibited Work: Chipping, core-drilling, or cutting into RCC columns, shear walls, and beams is strictly prohibited",
                "Balcony Grills: External facade alterations prohibited; only approved standard safety invisible grilles permitted",
                "Plumbing Modifications: Relocation of wet area toilet core drops strictly disallowed to prevent leakage to lower units",
            ]),
            ("Debris Handling & Service Elevator:", [
                "Transport: All construction materials and tile boxes must use designated Service Elevator only",
                "Debris Removal: All civil debris must be bagged in gunny bags and carted away within 48 hours; zero dumping in common refuse chutes",
                "Security Deposit: Refundable ₹50,000 interior fit-out deposit required with association prior to commencing work",
            ]),
        ],
    },
    {
        "filename": "Pet_Policy_and_Common_Area_Etiquette.pdf",
        "title": "Casagrand Aquagrove - Pet Policy & Common Area Etiquette",
        "subtitle": "[DEMONSTRATION & ARCHITECTURE REFERENCE DOCUMENT - SYNTHETIC DATASET]",
        "sections": [
            ("Pet Registration & Number Allowance:", [
                "Permitted Pets: Domestic dogs, cats, and birds permitted; maximum 2 domestic pets per household",
                "Registration: All pets must be registered with the Residents Welfare Association (RWA) with current rabies vaccination records",
            ]),
            ("Common Area Leash & Movement Rules:", [
                "Leash Requirement: Dogs must remain on a standard leash (maximum 1.5m length) at all times in common corridors and garden pathways",
                "Designated Pet Elevator: Residents with pets must use Elevator No. 3 (Service / Pet Elevator)",
                "Prohibited Zones: Pets are strictly prohibited inside the swimming pool deck, indoor badminton courts, and children's sandpit",
            ]),
            ("Dedicated Pet Agility Park & Hygiene:", [
                "Pet Park: 2,500 sq ft dedicated fenced off-leash dog agility park located on the northeastern garden periphery",
                "Waste Disposal: Pet owners must immediately scoop waste using biodegradable bags and deposit into designated green dog waste bins",
            ]),
        ],
    },
]

def create_pdf(doc_data: dict):
    pdf_path = PDF_DIR / doc_data["filename"]
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # Standard A4 size
    
    # Margin & Header
    margin_x = 45
    y = 50
    
    # Header block
    page.insert_text(
        (margin_x, y),
        doc_data["title"],
        fontsize=13,
        fontname="helv",
        fontfile=None,
        color=(0.05, 0.25, 0.35),
    )
    y += 18
    
    page.insert_text(
        (margin_x, y),
        doc_data["subtitle"],
        fontsize=9,
        fontname="helv",
        color=(0.4, 0.45, 0.5),
    )
    y += 15
    
    # Divider line
    page.draw_line((margin_x, y), (550, y), color=(0.1, 0.6, 0.65), width=1.5)
    y += 24
    
    for section_title, bullets in doc_data["sections"]:
        # Section Heading
        page.insert_text(
            (margin_x, y),
            section_title,
            fontsize=11,
            fontname="helv",
            color=(0.1, 0.45, 0.5),
        )
        y += 16
        
        for bullet in bullets:
            # Bullet point text with auto wrapping
            text = f"• {bullet}"
            # Simple line wrap if text exceeds width
            if len(text) > 85:
                part1 = text[:82]
                part2 = "    " + text[82:]
                page.insert_text((margin_x + 10, y), part1, fontsize=9.5, fontname="helv", color=(0.15, 0.15, 0.15))
                y += 14
                page.insert_text((margin_x + 10, y), part2, fontsize=9.5, fontname="helv", color=(0.15, 0.15, 0.15))
                y += 14
            else:
                page.insert_text((margin_x + 10, y), text, fontsize=9.5, fontname="helv", color=(0.15, 0.15, 0.15))
                y += 14
        
        y += 10
        if y > 780:
            page = doc.new_page(width=595, height=842)
            y = 50
            
    doc.save(str(pdf_path))
    doc.close()
    print(f"Generated: {pdf_path.name}")

if __name__ == "__main__":
    print(f"Generating {len(DOCUMENTS)} demonstration PDFs in {PDF_DIR}...")
    for doc in DOCUMENTS:
        create_pdf(doc)
    print("All demo documents successfully generated!")


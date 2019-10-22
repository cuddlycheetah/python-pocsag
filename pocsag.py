import ctypes
import struct
"""

** 11.09.2019 : Added Numeric Pager support by cuddlycheetah (github.com/cuddlycheetah)
** 14.10.2019 : Added Repeating Transmission + Single Preamble Mode (github.com/cuddlycheetah)
** 22.10.2019 : Made the Original (from rpitx) to a Python Encoder. (github.com/cuddlycheetah)
"""
#The sync word exists at the start of every batch.
#A batch is 16 words, a sync word occurs every 16 data words.
SYNC=0x7CD215D8

#The idle word is used as padding before the address word, at the end
#of a message to indicate that the message is finished. Interestingly, the
#idle word does not have a valid CRC code, the sync word does.
IDLE=0x7A89C197

#One frame consists of a pair of two words
FRAME_SIZE = 2

#One batch consists of 8 frames, 16 words
BATCH_SIZE = 16

#The preamble comes before a message, is a series of alternating
#1,0,1,0... bits, at least 576 bits. It exists to allow the receiver
#to synchronize with the transmitter
PREAMBLE_LENGTH = 576

#These bits appear as the first bit of a word, for an address word and
#one for a data word
FLAG_ADDRESS = 0x000000
FLAG_MESSAGE = 0x100000

#The last two bits of an address word's data represent the data type
#0x3 for text, 0x0 for numeric.
FLAG_TEXT_DATA = 0x3
FLAG_NUMERIC_DATA = 0x0

#Each data word can contain 20 bits of text information. Each character is
#7 bits wide, encoded. The bit order of the characters is reversed from
#the normal bit order; the most significant bit of a word corresponds to the
#least significant bit of a character it is encoding. The characters are split
#across the words of a message to ensure maximal usage of all bits.
TEXT_BITS_PER_WORD = 20

#As mentioned above, are 7 bit ASCII encoded
TEXT_BITS_PER_CHAR = 7

NUMERIC_BITS_PER_WORD = 20
NUMERIC_BITS_PER_DIGIT = 4

#Length of CRC codes in bits
CRC_BITS=10

#The CRC generator polynomial
CRC_GENERATOR=0b11101101001





'''*
 * Calculate the CRC error checking code for the given word.
 * Messages use a 10 bit CRC computed from the 21 data bits.
 * This is calculated through a binary polynomial long division, returning
 * the remainder.
 * See https:#en.wikipedia.org/wiki/Cyclic_redundancy_check#Computation
 * for more information.
'''
def crc(inputMsg):
    #Align MSB of denominatorerator with MSB of message
    denominator = CRC_GENERATOR << 20

    #Message is right-padded with zeroes to the message length + crc length
    msg = inputMsg << CRC_BITS

    #We iterate until denominator has been right-shifted back to it's original value.
    for column in range(20 + 1):
        #Bit for the column we're aligned to
        msgBit = (msg >> (30 - column)) & 1

        #If the current bit is zero, don't modify the message self iteration
        if msgBit != 0:
            #While we would normally subtract in long division, XOR here.
            msg ^= denominator


        #Shift the denominator over to align with the next column
        denominator >>= 1


    #At self point 'msg' contains the CRC value we've calculated
    return msg & 0x3FF

'''*
 * Calculates the even parity bit for a message.
 * If the number of bits in the message is even, 0, return 1.
'''
def parity(x):
    #Our parity bit
    p = 0

    #We xor p with each bit of the input value. This works because
    #xoring two one-bits will cancel out and leave a zero bit.  Thus
    #xoring any even number of one bits will result in zero, xoring
    #any odd number of one bits will result in one.
    for i in range(32):
        p ^= (x & 1)
        x >>= 1

    return p

'''*
 * Encodes a 21-bit message by calculating and adding a CRC code and parity bit.
'''
def encodeCodeword(msg):
    fullCRC = (msg << CRC_BITS) | crc(msg)
    p = parity(fullCRC)
    return (fullCRC << 1) | p

'''*
 * ASCII encode a null-terminated string as a series of codewords, written
 * to (*out). Returns the number of codewords written. Caller should ensure
 * that enough memory is allocated in (*out) to contain the message
 *
 * initial_offset indicates which word in the current batch the function is
 * beginning at, that it can insert SYNC words at appropriate locations.
'''
def encodeASCII(initial_offset, text, buff):
    #Number of words written to *out
    numWordsWritten = 0

    #Data for the current word we're writing
    currentWord = 0
    #Nnumber of bits we've written so far to the current word
    currentNumBits = 0

    #Position of current word in the current batch
    wordPosition = initial_offset

    for c in text:
        #Encode the character bits backwards
        for i in range(TEXT_BITS_PER_CHAR):
            currentWord <<= 1
            currentWord |= (ord(c) >> i) & 1
            currentNumBits+=1
            if currentNumBits == TEXT_BITS_PER_WORD:
                #Add the MESSAGE flag to our current word and encode it.
                buff.append(encodeCodeword(currentWord | FLAG_MESSAGE))
                currentWord = 0
                currentNumBits = 0
                numWordsWritten+=1

                wordPosition+=1
                if wordPosition == BATCH_SIZE:
                    #We've filled a full batch, to insert a SYNC word
                    #and start a one.
                    buff.append(SYNC)
                    numWordsWritten+=1
                    wordPosition = 0
    #Write remainder of message
    if currentNumBits > 0:
        #Pad out the word to 20 bits with zeroes
        currentWord <<= 20 - currentNumBits
        buff.append(encodeCodeword(currentWord | FLAG_MESSAGE))
        numWordsWritten+=1

        wordPosition+=1
        if wordPosition == BATCH_SIZE:
            #We've filled a full batch, to insert a SYNC word
            #and start a one.
            buff.append(SYNC)
            numWordsWritten+=1
            wordPosition = 0
    return numWordsWritten

# Char Translationtable
mirrorTab = [0x00, 0x08, 0x04, 0x0c, 0x02, 0x0a, 0x06, 0x0e, 0x01, 0x09]
def encodeDigit(ch):
    if ord(ch) >= ord('0') and ord(ch) <= ord('9'):
        return mirrorTab[ord(ch) - ord('0')]
    elif ch == ' ':
        return 0x03
    elif ch == 'u' or ch == 'U':
        return 0x0d
    elif ch == '-' or ch == '_':
        return 0x0b
    elif ch == '(' or ch == '[':
        return 0x0f
    elif ch == ')' or ch == ']':
        return 0x07
    else:
        return 0x05

def encodeNumeric(initial_offset, text, buff):
    #Number of words written to *out
    numWordsWritten = 0

    #Data for the current word we're writing
    currentWord = 0

    #Nnumber of bits we've written so far to the current word
    currentNumBits = 0

    #Position of current word in the current batch
    wordPosition = initial_offset

    for c in text:
        #Encode the digit bits backwards
        for i in range(NUMERIC_BITS_PER_DIGIT):
            currentWord <<= 1
            digit = encodeDigit(c)
            digit = ((digit & 1) << 3) | ((digit & 2) << 1) | ((digit & 4) >> 1) | ((digit & 8) >> 3)

            currentWord |= (digit >> i) & 1
            currentNumBits+=1
            if currentNumBits == NUMERIC_BITS_PER_WORD:
                #Add the MESSAGE flag to our current word and encode it.
                buff.append(encodeCodeword(currentWord | FLAG_MESSAGE))
                currentWord = 0
                currentNumBits = 0
                numWordsWritten+=1

                wordPosition+=1
                if wordPosition == BATCH_SIZE:
                    #We've filled a full batch, to insert a SYNC word
                    #and start a one.
                    buff.append(SYNC)
                    numWordsWritten+=1
                    wordPosition = 0
    #Write remainder of message
    if currentNumBits > 0:
        #Pad out the word to 20 bits with zeroes
        currentWord <<= 20 - currentNumBits
        buff.append(encodeCodeword(currentWord | FLAG_MESSAGE))
        numWordsWritten+=1

        wordPosition+=1
        if wordPosition == BATCH_SIZE:
            #We've filled a full batch, to insert a SYNC word
            #and start a one.
            buff.append(SYNC)
            numWordsWritten+=1
            wordPosition = 0
    return numWordsWritten

'''*
 * An address of 21 bits, only 18 of those bits are encoded in the address
 * word itself. The remaining 3 bits are derived from which frame in the batch
 * is the address word. This calculates the number of words (not framesnot )
 * which must precede the address word so that it is in the right spot. These
 * words will be filled with the idle value.
'''
def addressOffset(address):
    return (address & 0x7) * FRAME_SIZE

'''*
 * Calculates the length in words of a text POCSAG message, the address
 * and the number of characters to be transmitted.
 '''
def textMessageLength(repeatIndex, address, numChars):
    numWords = 0

    #Padding before address word.
    numWords += addressOffset(address)

    #Address word itself
    numWords+=1

    #numChars * 7 bits per character / 20 bits per word, up
    numWords += (numChars * TEXT_BITS_PER_CHAR + (TEXT_BITS_PER_WORD - 1)) / TEXT_BITS_PER_WORD

    #Idle word representing end of message
    numWords+=1

    #Pad out last batch with idles
    numWords += BATCH_SIZE - (numWords % BATCH_SIZE)

    #Batches consist of 16 words each and are preceded by a sync word.
    #So we add one word for every 16 message words
    numWords += numWords / BATCH_SIZE

    #Preamble of 576 alternating 1,0,1, bits before the message
    #Even though self comes first, add it to the length last so it
    #doesn't affect the other word-based calculations
    if repeatIndex == 0:
        numWords += PREAMBLE_LENGTH / 32

    return numWords


'''*
 * Calculates the length in words of a numeric POCSAG message, the address
 * and the number of characters to be transmitted.
'''
def numericMessageLength(repeatIndex, address, numChars):
    numWords = 0

    #Padding before address word.
    numWords += addressOffset(address)

    #Address word itself
    numWords+=1

    #numChars * 7 bits per character / 20 bits per word, up
    numWords += (numChars * NUMERIC_BITS_PER_DIGIT + (NUMERIC_BITS_PER_WORD - 1)) / NUMERIC_BITS_PER_WORD

    #Idle word representing end of message
    numWords+=1

    #Pad out last batch with idles
    numWords += BATCH_SIZE - (numWords % BATCH_SIZE)

    #Batches consist of 16 words each and are preceded by a sync word.
    #So we add one word for every 16 message words
    numWords += numWords / BATCH_SIZE

    #Preamble of 576 alternating 1,0,1, bits before the message
    #Even though self comes first, add it to the length last so it
    #doesn't affect the other word-based calculations
    if repeatIndex == 0:
        numWords += PREAMBLE_LENGTH / 32

    return numWords


def encodeTransmission(numeric, repeatIndex, address, fb, message, buff):
    out=0
    #Encode preamble
    #Alternating 1,0,1, bits for 576 bits, for receiver to synchronize
    #with transmitter
    if repeatIndex == 0:
        for i in range(PREAMBLE_LENGTH / 32):
            buff.append(0xAAAAAAAA)
            out+=1
    start = out

    #Sync
    buff.append(SYNC)
    out+=1

    #Write out padding before adderss word
    prefixLength = addressOffset(address)
    for i in range(prefixLength):
        buff.append(IDLE)
        out+=1

    #Write address word.
    #The last two bits of word's data contain the message type (function bits)
    #The 3 least significant bits are dropped, those are encoded by the
    #word's location.
    buff.append(encodeCodeword(((address >> 3) << 2) | fb))
    out+=1

    #Encode the message itself
    if numeric == True:
        out += encodeNumeric(addressOffset(address) + 1, message, buff)
    else:
        out += encodeASCII(addressOffset(address) + 1, message, buff)


    #Finally, an IDLE word indicating the end of the message
    buff.append(IDLE)
    out+=1

    #Pad out the last batch with IDLE to write multiple of BATCH_SIZE + 1
    #words (+ 1 is there because of the SYNC words)
    written = out - start
    padding = (BATCH_SIZE + 1) - written % (BATCH_SIZE + 1)
    for i in range(padding):
        buff.append(IDLE)
        out+=1

def parseAddress(address):
    if address.find('A') > 0:
        return [address[:address.index('A')], 0]
    elif address.find('B') > 0:
        return [address[:address.index('B')], 1]
    elif address.find('C') > 0:
        return [address[:address.index('C')], 2]
    elif address.find('D') > 0:
        return [address[:address.index('D')], 3]
    else:
        return [address, 3]

def encodeTXBatch(messages, repeatNum = 2, inverted = False):
    transmission = []
    pocsagData = []
    msgIndex = 0
    for message in messages:
        msgNumeric = message[0]
        msgAddrParsed = parseAddress(message[1])
        msgAddress = int(msgAddrParsed[0])
        msgBits = msgAddrParsed[1]
        msgText = message[2]
        for repeat in range(repeatNum):
            encodeTransmission(msgNumeric, msgIndex, msgAddress, msgBits, msgText, transmission)
            msgIndex += 1
    for word in transmission:
        uint = ctypes.c_uint32(word).value
        if not inverted:
            uint = ~uint
        pocsagData.append(int((uint>>24) & 0xFF))
        pocsagData.append(int((uint>>16) & 0xFF))
        pocsagData.append(int((uint>>8) & 0xFF))
        pocsagData.append(int(uint & 0xFF))
    return pocsagData

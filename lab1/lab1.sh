#!/bin/bash
echo 'My id is 663040653-3'
echo 'These is My id count in this file'
grep -c '663040653-3' random_ids.txt
echo "copy grep result to output file"
grep '663040653-3' random_ids.txt > lab1output.txt
ls lab1output.txt -l
echo "New text result in lab1output.txt "
cat lab1output.txt 
